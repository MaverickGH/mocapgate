"""MoCapGate — игровые инструменты анимации на stdlib (без numpy).

Петля (make_loop), вынос root motion в отдельный сустав Root (extract_root_motion),
«в месте» (in_place), ремонт диапазона кадров (repair_range) и запись BVH, где
кроме корня позицию несёт и Hips (write_bvh).

Кадр: {"<joint>": {"rot": (z, x, y) градусы ZXY, "pos": (x, y, z) см — у корня}}.
FK: мир сустава = мир родителя + R_родителя · (offset + pos); R = R_родителя · R_локальный.
Y вверх, «вперёд» тела в покое — +Z, рысканье (yaw) — поворот вокруг Y.
"""
from __future__ import annotations
import math
from core.skeleton import Joint
from core.rotations import (euler_zxy_to_matrix, matrix_to_euler_zxy, continuous_euler, matmul,
                            mat_vec, matrix_to_quat, quat_to_matrix, slerp)

_I = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


# ---------------------------------------------------------------- общие помощники

def _bare(name: str) -> str:
    return name.split(':')[-1]


def _copy(frames):
    return [{j: dict(d) for j, d in fr.items()} for fr in frames]


def _q(rot):
    return matrix_to_quat(euler_zxy_to_matrix(*rot))


def _euler(m, prev):
    return continuous_euler(matrix_to_euler_zxy(m), prev)


def _ry(deg):
    return euler_zxy_to_matrix(0.0, 0.0, deg)


def _smooth(t):
    return t * t * (3 - 2 * t)


def _angle(qa, qb) -> float:
    d = min(1.0, abs(sum(p * q for p, q in zip(qa, qb))))
    return math.degrees(2 * math.acos(d))


def _yaw(m, prev=None) -> float:
    """Курс тела: направление +Z сустава, спроецированное на пол (градусы, без скачков 360°)."""
    f = mat_vec(m, (0.0, 0.0, 1.0))
    if f[0] * f[0] + f[2] * f[2] < 1e-12:
        return prev or 0.0
    a = math.degrees(math.atan2(f[0], f[2]))
    return a if prev is None else a + 360.0 * round((prev - a) / 360.0)


def _root_pos(fr, name):
    return tuple(fr.get(name, {}).get('pos', (0.0, 0.0, 0.0)))


def world_positions(root: Joint, frame: dict) -> dict:
    """Мировые позиции всех суставов (и End Site как '<имя>/end') одного кадра, см."""
    out = {}

    def walk(j, ppos, prot):
        d = frame.get(j.name, {})
        off = j.offset
        if 'pos' in d:
            off = tuple(o + p for o, p in zip(off, d['pos']))
        pos = tuple(a + b for a, b in zip(ppos, mat_vec(prot, off)))
        rot = matmul(prot, euler_zxy_to_matrix(*d.get('rot', (0.0, 0.0, 0.0))))
        out[j.name] = pos
        if j.end_offset is not None:
            out[j.name + '/end'] = tuple(a + b for a, b in zip(pos, mat_vec(rot, j.end_offset)))
        for c in j.children:
            walk(c, pos, rot)

    walk(root, (0.0, 0.0, 0.0), _I)
    return out


# ---------------------------------------------------------------- петля

def _seam(seq, rn, travel, fps):
    a, b = seq[-1], seq[0]
    rot = max((_angle(_q(a[j]['rot']), _q(b[j]['rot'])) for j in a if j in b and 'rot' in a[j] and 'rot' in b[j]),
              default=0.0)
    p = [_root_pos(seq[i], rn) for i in (-2, -1, 0, 1)]
    nxt = (p[2][0] + travel[0], p[2][1], p[2][2] + travel[1])
    v_prev = [p[1][i] - p[0][i] for i in range(3)]
    v_seam = [nxt[i] - p[1][i] for i in range(3)]
    v_next = [p[3][i] - p[2][i] for i in range(3)]
    jump = max(math.dist(v_seam, v_prev), math.dist(v_seam, v_next)) * fps
    return {'rotation_deg': rot, 'root_velocity_jump_cm_s': jump}


def make_loop(root: Joint, frames: list, fps: float, blend_seconds: float = 0.3, keep_travel: bool = True):
    """Бесшовная петля: последние N кадров плавно переходят в первые N, клип начинается с кадра N.

    Результат на N кадров короче: out[-1] → out[0] — обычный шаг движения. Дрейф курса
    (yaw) за цикл убирается равномерно по всему клипу. keep_travel=True — для root motion:
    следующий цикл начинается со смещением info['travel_cm'] и той же скоростью;
    False — «на месте»: линейный уход по X/Z вычитается, корень возвращается в начало.
    Возвращает (frames, info); info['seam_before'/'seam_after'] — максимальная разница
    поворота суставов на стыке (°) и скачок скорости корня (см/с).
    """
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or not math.isfinite(fps) or fps <= 0:
        raise ValueError('FPS должен быть положительным числом')
    if not isinstance(blend_seconds, (int, float)) or not math.isfinite(blend_seconds) or blend_seconds < 0:
        raise ValueError('Длительность смешивания не может быть отрицательной')
    n, N = len(frames), max(1, round(blend_seconds * fps))
    if n < 2 * N + 2:
        raise ValueError(f'Клип слишком короткий для петли: нужно минимум {2 * N + 2} кадров при смешивании {N} кадров')
    rn, L = root.name, n - N
    fr = _copy(frames)
    raw = [_root_pos(f, rn) for f in fr]
    before = _seam(fr, rn, (raw[-1][0] - raw[0][0], raw[-1][2] - raw[0][2]) if keep_travel else (0.0, 0.0), fps)

    # дрейф курса за цикл (окно конца против окна начала) раскладываем линейно по клипу
    ms = [euler_zxy_to_matrix(*f[rn].get('rot', (0.0, 0.0, 0.0))) for f in fr]
    yaw, prev = [], None
    for m in ms:
        prev = _yaw(m, prev)
        yaw.append(prev)
    drift = sum(yaw[L + k] - yaw[k] for k in range(N)) / N
    pos, prev_rot = [raw[0]], None
    for i in range(n):
        c = _ry(-drift * i / L)
        if i:
            d = mat_vec(c, [raw[i][j] - raw[i - 1][j] for j in range(3)])
            pos.append((pos[-1][0] + d[0], raw[i][1], pos[-1][2] + d[2]))
        prev_rot = _euler(matmul(c, ms[i]), prev_rot)
        fr[i].setdefault(rn, {})['rot'] = prev_rot
    travel = tuple(sum(pos[L + k][j] - pos[k][j] for k in range(N)) / N for j in (0, 2))
    if not keep_travel:
        pos = [(p[0] - travel[0] * i / L, p[1], p[2] - travel[1] * i / L) for i, p in enumerate(pos)]
        travel = (0.0, 0.0)
    for i, p in enumerate(pos):
        fr[i][rn]['pos'] = p

    # хвост → голова (голова сдвинута на travel)
    for k in range(N):
        i, w = L + k, _smooth((k + 1) / N)
        a, b = fr[i], fr[k]
        pa, pb = a[rn]['pos'], b[rn]['pos']
        tgt = (pb[0] + travel[0], pb[1], pb[2] + travel[1])
        a[rn]['pos'] = tuple(x + (y - x) * w for x, y in zip(pa, tgt))
        for j, d in a.items():
            if 'rot' in d and 'rot' in b.get(j, {}):
                d['rot'] = quat_to_matrix(slerp(_q(d['rot']), _q(b[j]['rot']), w))
    out = fr[N:]
    for idx in range(L - N, L):  # непрерывные углы Эйлера после смешивания
        for j, d in out[idx].items():
            if 'rot' in d and isinstance(d['rot'][0], tuple):
                d['rot'] = _euler(d['rot'], out[idx - 1].get(j, {}).get('rot') if idx else None)
    after = _seam(out, rn, travel, fps)
    return out, {'frames': L, 'blend_frames': N, 'travel_cm': travel, 'yaw_drift_deg': drift,
                 'seam_before': before, 'seam_after': after}


# ---------------------------------------------------------------- root motion

def extract_root_motion(root: Joint, frames: list, mode: str = 'ground'):
    """Новый верхний сустав Root (в начале координат) над старым корнем (Hips).

    mode='ground' — Root несёт X/Z бёдер на полу и курс (yaw) бёдер;
    mode='translation' — только X/Z. Hips получает оффсет 0 и локальную позицию
    (0, высота, 0) плюс оставшийся наклон/крен — мировые позы не меняются.
    Записывать через write_bvh: у Hips появляются каналы позиции.
    """
    if mode not in ('ground', 'translation'):
        raise ValueError("Режим root motion: 'ground' (X/Z и курс) или 'translation' (только X/Z)")
    if any(_bare(n) == 'Root' for n in _names(root)):
        raise ValueError('В скелете уже есть сустав Root')
    rn = root.name
    prefix = rn[:-len(_bare(rn))]
    rname = prefix + 'Root'
    hips = Joint(rn, (0.0, 0.0, 0.0), list(root.children), root.end_offset)
    new_root = Joint(rname, (0.0, 0.0, 0.0), [hips])
    out, prev_yaw, prev_rot = [], None, None
    for fr in frames:
        d = fr.get(rn, {})
        h = tuple(o + p for o, p in zip(root.offset, d.get('pos', (0.0, 0.0, 0.0))))
        m = euler_zxy_to_matrix(*d.get('rot', (0.0, 0.0, 0.0)))
        nf = {j: dict(v) for j, v in fr.items()}
        if mode == 'ground':
            prev_yaw = _yaw(m, prev_yaw)
            prev_rot = _euler(matmul(_ry(-prev_yaw), m), prev_rot)
            nf[rname] = {'pos': (h[0], 0.0, h[2]), 'rot': (0.0, 0.0, prev_yaw)}
            nf[rn] = {**nf.get(rn, {}), 'pos': (0.0, h[1], 0.0), 'rot': prev_rot}
        else:
            nf[rname] = {'pos': (h[0], 0.0, h[2]), 'rot': (0.0, 0.0, 0.0)}
            nf[rn] = {**nf.get(rn, {}), 'pos': (0.0, h[1], 0.0), 'rot': tuple(d.get('rot', (0.0, 0.0, 0.0)))}
        out.append(nf)
    return new_root, out


def in_place(frames: list, root_name: str) -> list:
    """Обнулить горизонтальное смещение корня (X/Z), высота остаётся."""
    out = _copy(frames)
    for fr in out:
        if root_name in fr and 'pos' in fr[root_name]:
            p = fr[root_name]['pos']
            fr[root_name]['pos'] = (0.0, p[1], 0.0)
    return out


def _names(root: Joint) -> list:
    res = [root.name]
    for c in root.children:
        res.extend(_names(c))
    return res


# ---------------------------------------------------------------- ремонт диапазона

def repair_range(root: Joint, frames: list, first: int, last: int, joints=None) -> list:
    """Заменить кадры first..last (с 0, включительно) плавным переходом между соседями.

    Повороты — slerp между кадрами first-1 и last+1, позиция корня — кубический
    Эрмит по скоростям соседей. Если диапазон касается начала/конца клипа — держим
    ближайший целый кадр. joints=None — все суставы, иначе только перечисленные
    (имена без учёта префикса вроде 'mixamorig:'). Остальные кадры не меняются.
    """
    n = len(frames)
    if type(first) is not int or type(last) is not int:
        raise ValueError('Границы диапазона должны быть целыми номерами кадров')
    if not 0 <= first <= last < n:
        raise ValueError(f'Диапазон {first}–{last} вне клипа: допустимы кадры 0–{n - 1}')
    if first == 0 and last == n - 1:
        raise ValueError('Нельзя заменить весь клип: нужен хотя бы один целый соседний кадр')
    all_names = _names(root)
    if joints is None:
        sel = set(all_names)
    else:
        if isinstance(joints, str):
            joints = [joints]
        by_bare = {_bare(x): x for x in all_names}
        missing = [j for j in joints if _bare(j) not in by_bare]
        if missing:
            raise ValueError('Нет таких суставов в скелете: ' + ', '.join(missing))
        sel = {by_bare[_bare(j)] for j in joints}
    out = _copy(frames)
    rn = root.name
    a, b = first - 1, last + 1
    if a < 0 or b >= n:
        src = frames[b if a < 0 else a]
        for i in range(first, last + 1):
            for j in sel:
                if j in src:
                    out[i].setdefault(j, {}).update({k: v for k, v in src[j].items() if k in ('rot', 'pos')})
        return out
    S = b - a
    fa, fb = frames[a], frames[b]
    pa, pb = _root_pos(fa, rn), _root_pos(fb, rn)
    m0 = [pa[k] - _root_pos(frames[a - 1], rn)[k] for k in range(3)] if a > 0 else [(pb[k] - pa[k]) / S for k in range(3)]
    m1 = [_root_pos(frames[b + 1], rn)[k] - pb[k] for k in range(3)] if b + 1 < n else [(pb[k] - pa[k]) / S for k in range(3)]
    for i in range(first, last + 1):
        t = (i - a) / S
        for j in sel:
            da, db = fa.get(j, {}), fb.get(j, {})
            if 'rot' in da and 'rot' in db:
                q = slerp(_q(da['rot']), _q(db['rot']), t)
                out[i].setdefault(j, {})['rot'] = _euler(quat_to_matrix(q), out[i - 1].get(j, {}).get('rot'))
        if rn in sel and 'pos' in fa.get(rn, {}) and 'pos' in fb.get(rn, {}):
            h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            out[i].setdefault(rn, {})['pos'] = tuple(h00 * pa[k] + h10 * S * m0[k] + h01 * pb[k] + h11 * S * m1[k]
                                                     for k in range(3))
    return out


# ---------------------------------------------------------------- запись BVH

_ROT = ('Zrotation', 'Xrotation', 'Yrotation')
_POS = ('Xposition', 'Yposition', 'Zposition')


def write_bvh(root: Joint, frames: list, frame_time: float = 1 / 30) -> str:
    """BVH, где 6 каналов у корня и у каждого сустава, у которого в кадрах есть 'pos'.

    Нужно для результата extract_root_motion (Hips несёт высоту). core.bvh.write
    пишет позицию только корню и высоту Hips потеряет. Сохранять — core.bvh.save.
    """
    moving = {j for fr in frames for j, d in fr.items() if 'pos' in d}
    lines, channels = ['HIERARCHY'], []

    def fmt(off):
        return f'{off[0]:g} {off[1]:g} {off[2]:g}'

    def walk(j, depth, is_root):
        pad = '  ' * depth
        lines.extend([f"{pad}{'ROOT' if is_root else 'JOINT'} {j.name}", f'{pad}{{', f'{pad}  OFFSET {fmt(j.offset)}'])
        cs = _POS + _ROT if is_root or j.name in moving else _ROT
        lines.append(f"{pad}  CHANNELS {len(cs)} {' '.join(cs)}")
        channels.extend((j.name, c) for c in cs)
        for c in j.children:
            walk(c, depth + 1, False)
        if j.end_offset is not None:
            lines.extend([f'{pad}  End Site', f'{pad}  {{', f'{pad}    OFFSET {fmt(j.end_offset)}', f'{pad}  }}'])
        lines.append(f'{pad}}}')

    walk(root, 0, True)
    lines += ['MOTION', f'Frames: {len(frames)}', f'Frame Time: {frame_time:.12f}']
    for fr in frames:
        row = []
        for j, c in channels:
            d = fr.get(j, {})
            row.append(f"{d.get('pos', (0, 0, 0))[_POS.index(c)]:.6f}" if c in _POS
                       else f"{d.get('rot', (0, 0, 0))[_ROT.index(c)]:.6f}")
        lines.append(' '.join(row))
    return '\n'.join(lines) + '\n'
