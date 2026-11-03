"""MoCapGate — правка готовой анимации на stdlib (без numpy).

Зеркало лево↔право (mirror, pairs), перенос/поворот/масштаб пути и посадка на пол
(transform), смена скорости и частоты кадров (retime, speed_ramp), плавный вход и
выход из позы (ease). Все функции возвращают новые кадры и не меняют входные.

Кадр: {"<joint>": {"rot": (z, x, y) градусы ZXY, "pos": (x, y, z) см}}; 'pos' может
быть у любого сустава. Y вверх, тело в покое смотрит на +Z, левая сторона — +X.
Имена суставов могут нести префикс вроде 'mixamorig:'.
"""
from __future__ import annotations
import bisect
import math
import re
from core.skeleton import Joint
from core.rotations import continuous_euler, matrix_to_euler_zxy, quat_to_matrix, slerp

__all__ = ['pairs', 'mirror', 'transform', 'retime', 'speed_ramp', 'ease']


# ---------------------------------------------------------------- общие помощники

def _bare(name: str) -> str:
    return name.split(':')[-1]


def _check_frames(frames):
    if not isinstance(frames, (list, tuple)) or not frames:
        raise ValueError('Нет кадров анимации')
    if not all(isinstance(fr, dict) for fr in frames):
        raise ValueError('Каждый кадр должен быть словарём суставов')


def _num(value, what, positive=False):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{what}: нужно число') from None
    if not math.isfinite(v):
        raise ValueError(f'{what}: нужно конечное число')
    if positive and v <= 0:
        raise ValueError(f'{what}: нужно число больше нуля')
    return v


def _vec3(value, what):
    try:
        v = tuple(float(c) for c in value)
    except (TypeError, ValueError):
        raise ValueError(f'{what}: нужны три числа (x, y, z)') from None
    if len(v) != 3 or not all(math.isfinite(c) for c in v):
        raise ValueError(f'{what}: нужны три конечных числа (x, y, z)')
    return v


def _copy(frames):
    return [{j: dict(d) for j, d in fr.items()} for fr in frames]


def _walk(root: Joint):
    stack = [root]
    while stack:
        j = stack.pop()
        yield j
        stack.extend(reversed(j.children))


def _e2q(rot):
    """Эйлер ZXY (градусы) → кватернион (w, x, y, z) для R = Rz·Rx·Ry, без матриц."""
    hz, hx, hy = (math.radians(a) * 0.5 for a in rot)
    cz, sz, cx, sx, cy, sy = math.cos(hz), math.sin(hz), math.cos(hx), math.sin(hx), math.cos(hy), math.sin(hy)
    a, b, c, d = cz * cx, cz * sx, sz * sx, sz * cx  # qz·qx
    return (a * cy - c * sy, b * cy - d * sy, a * sy + c * cy, b * sy + d * cy)


def _q2e(q, prev):
    return continuous_euler(matrix_to_euler_zxy(quat_to_matrix(q)), prev)


def _qmul(p, q):
    a1, b1, c1, d1 = p
    a2, b2, c2, d2 = q
    return (a1 * a2 - b1 * b2 - c1 * c2 - d1 * d2, a1 * b2 + b1 * a2 + c1 * d2 - d1 * c2,
            a1 * c2 - b1 * d2 + c1 * a2 + d1 * b2, a1 * d2 + b1 * c2 - c1 * b2 + d1 * a2)


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _lerp(a, b, t):
    return tuple(p + t * (r - p) for p, r in zip(a, b))


# ---------------------------------------------------------------- пары лево/право

_WORD = re.compile(r'left|right', re.I)
_TOKEN = re.compile(r'(^|[ ._\-])([lLrR])(?=$|[ ._\-\d])')
_CAMEL = re.compile(r'^([lr])(?=[A-Z])')  # lShldr / rThigh (DAZ, CMU)
_SWAP = {'l': 'r', 'r': 'l', 'L': 'R', 'R': 'L'}


def _swap_word(m):
    w = m.group(0)
    new = 'right' if w.lower() == 'left' else 'left'
    if w.isupper():
        return new.upper()
    return new.capitalize() if w[0].isupper() else new


def _candidates(bare):
    for rx, fn in ((_WORD, _swap_word),
                   (_TOKEN, lambda m: m.group(1) + _SWAP[m.group(2)]),
                   (_CAMEL, lambda m: _SWAP[m.group(1)])):
        s = rx.sub(fn, bare)
        if s != bare:
            yield s


def pairs(names) -> dict:
    """Пары «левый ↔ правый»: {имя: имя напарника} только для суставов, у которых напарник есть.

    Понимает Left*/Right* (Mixamo, SOMA, внутри имени тоже: LeftHandThumb1, Hand_Left),
    суффиксы _l/_r, .L/.R, -L/-R (UE thigh_l, Rigify upper_arm.L.001), префиксы l_/r_ и L_/R_
    (SMPL), «Bip01 L Thigh», lShldr/rShldr. Регистр и префикс вида 'mixamorig:' не важны;
    при равенстве предпочитается напарник с тем же префиксом.
    """
    names = list(names)
    full = {n.lower(): n for n in names}
    by_bare: dict = {}
    for n in names:
        by_bare.setdefault(_bare(n).lower(), n)
    out = {}
    for n in names:
        bare = _bare(n)
        prefix = n[:len(n) - len(bare)]
        for cand in _candidates(bare):
            mate = full.get((prefix + cand).lower()) or by_bare.get(cand.lower())
            if mate is not None and mate != n:
                out[n] = mate
                break
    return out


# ---------------------------------------------------------------- зеркало

def _mx(v):
    return (-v[0], v[1], v[2])


def _mirror_rot(rot):
    """Отражение X → −X: S·R·S при S = diag(−1, 1, 1).

    Для кватерниона это (w, x, −y, −z); в Эйлере ZXY то же самое точно и без
    пересчёта: Rz(−z)·Rx(x)·Ry(−y) — кривые остаются непрерывными, двойное зеркало
    возвращает исходные числа бит в бит.
    """
    z, x, y = rot
    return (-z, x, -y)


def mirror(root: Joint, frames: list):
    """Зеркальная копия движения: левое ↔ правое, отражение через плоскость YZ (X → −X).

    Каждый сустав получает отражённый поворот своего напарника (pairs), позиции
    ('pos' у корня и у любых суставов) — с обратным X. Скелет тоже отражается:
    оффсеты и End Site меняются местами с напарником и получают −X, поэтому
    несимметричный риг остаётся корректным. Возвращает (новый корень, новые кадры).
    """
    if not isinstance(root, Joint):
        raise ValueError('Нужен скелет (корневой сустав)')
    _check_frames(frames)
    joints = list(_walk(root))
    names = [j.name for j in joints]
    extra = {n for fr in frames for n in fr} - set(names)
    mate = pairs(names + sorted(extra))
    by_name = {j.name: j for j in joints}

    def build(j):
        src = by_name.get(mate.get(j.name, j.name), j)
        end = src.end_offset if src.end_offset is not None else j.end_offset
        return Joint(j.name, _mx(src.offset), [build(c) for c in j.children],
                     _mx(end) if end is not None else None)

    out = []
    for fr in frames:
        new = {}
        for name in fr:
            d = fr.get(mate.get(name, name)) or fr[name]
            nd = dict(d)
            if 'rot' in d:
                nd['rot'] = _mirror_rot(d['rot'])
            if 'pos' in d:
                nd['pos'] = _mx(d['pos'])
            new[name] = nd
        out.append(new)
    return build(root), out


# ---------------------------------------------------------------- перенос, поворот, масштаб, пол

_FLOOR_WORDS = ('foot', 'toe', 'ball', 'ankle', 'heel')


def _fk_min_y(root: Joint, frames, picked: set) -> float:
    """Самая низкая высота выбранных точек (суставы и '<имя>/end') по всему клипу, см."""
    best = math.inf
    for fr in frames:
        stack = [(root, (0.0, 0.0, 0.0), None)]
        while stack:
            j, ppos, pm = stack.pop()
            d = fr.get(j.name, {})
            off = j.offset
            if 'pos' in d:
                p = d['pos']
                off = (off[0] + p[0], off[1] + p[1], off[2] + p[2])
            if pm is None:
                pos = off
            else:
                pos = tuple(ppos[i] + pm[i][0] * off[0] + pm[i][1] * off[1] + pm[i][2] * off[2] for i in range(3))
            lm = quat_to_matrix(_e2q(d['rot'])) if 'rot' in d else None
            if pm is None:
                m = lm or ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
            elif lm is None:
                m = pm
            else:
                m = tuple(tuple(pm[i][0] * lm[0][k] + pm[i][1] * lm[1][k] + pm[i][2] * lm[2][k] for k in range(3))
                          for i in range(3))
            if j.name in picked and pos[1] < best:
                best = pos[1]
            if j.end_offset is not None and j.name + '/end' in picked:
                e = j.end_offset
                y = pos[1] + m[1][0] * e[0] + m[1][1] * e[1] + m[1][2] * e[2]
                if y < best:
                    best = y
            for c in j.children:
                stack.append((c, pos, m))
    return best


def _floor_points(root: Joint) -> set:
    """Стопы/пальцы и их End Site; если таких имён нет — все суставы и все End Site."""
    picked = set()

    def walk(j, inside):
        inside = inside or any(w in _bare(j.name).lower() for w in _FLOOR_WORDS)
        if inside:
            picked.add(j.name)
            if j.end_offset is not None:
                picked.add(j.name + '/end')
        for c in j.children:
            walk(c, inside)

    walk(root, False)
    if not picked:
        for j in _walk(root):
            picked.add(j.name)
            if j.end_offset is not None:
                picked.add(j.name + '/end')
    return picked


def transform(root: Joint, frames: list, offset=(0.0, 0.0, 0.0), scale: float = 1.0,
              yaw_deg: float = 0.0, floor_to_zero: bool = False) -> list:
    """Переместить всё движение целиком.

    Порядок: масштаб пути корня → поворот вокруг вертикальной оси через начало
    координат → сдвиг → (по желанию) посадка на пол.
    scale — множитель перемещения корня, длины костей не меняются: X/Z умножаются
    целиком, по Y масштабируется только отклонение от высоты первого кадра (рост
    стоящего персонажа сохраняется, подпрыгивания растут/уменьшаются).
    yaw_deg — поворот всего клипа вокруг Y (градусы, против часовой при взгляде сверху).
    offset — сдвиг в см (x, y, z). floor_to_zero — сдвиг по Y так, чтобы самая низкая
    точка стоп/пальцев (по FK, за весь клип) оказалась ровно на 0.
    """
    if not isinstance(root, Joint):
        raise ValueError('Нужен скелет (корневой сустав)')
    _check_frames(frames)
    t = _vec3(offset, 'Сдвиг')
    s = _num(scale, 'Масштаб пути', positive=True)
    yaw = _num(yaw_deg, 'Поворот')
    rn = root.name
    c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    qy = (math.cos(math.radians(yaw) / 2), 0.0, math.sin(math.radians(yaw) / 2), 0.0)
    off = root.offset
    y0 = frames[0].get(rn, {}).get('pos', (0.0, 0.0, 0.0))[1]
    out, prev = _copy(frames), None
    for fr in out:
        d = fr.setdefault(rn, {})
        p = d.get('pos', (0.0, 0.0, 0.0))
        p = (p[0] * s, y0 + (p[1] - y0) * s, p[2] * s)
        w = (off[0] + p[0], off[1] + p[1], off[2] + p[2])            # мир корня
        w = (c * w[0] + sn * w[2] + t[0], w[1] + t[1], -sn * w[0] + c * w[2] + t[2])  # Ry·w + t
        d['pos'] = (w[0] - off[0], w[1] - off[1], w[2] - off[2])
        if yaw:
            rot = d.get('rot', (0.0, 0.0, 0.0))
            d['rot'] = prev = _q2e(_qmul(qy, _e2q(rot)), prev)
    if floor_to_zero:
        low = _fk_min_y(root, out, _floor_points(root))
        if math.isfinite(low) and low:
            for fr in out:
                p = fr[rn]['pos']
                fr[rn]['pos'] = (p[0], p[1] - low, p[2])
    return out


# ---------------------------------------------------------------- скорость и частота кадров

def _resample(frames, fps, times):
    """Кадры в моменты исходного времени times (с): slerp поворотов, линейно 'pos'."""
    n = len(frames)
    quats: dict = {}

    def q(i, name):
        key = (i, name)
        v = quats.get(key)
        if v is None:
            v = quats[key] = _e2q(frames[i][name]['rot'])
        return v

    out, prev = [], {}
    for s in times:
        u = min(max(s * fps, 0.0), n - 1.0)
        i = int(u)
        a = u - i
        if i >= n - 1:
            i, a = n - 1, 0.0
        if a < 1e-9 or a > 1 - 1e-9:
            src = frames[i + 1] if a > 0.5 else frames[i]
            fr = {j: dict(d) for j, d in src.items()}
        else:
            fa, fb = frames[i], frames[i + 1]
            fr = {}
            for j, da in fa.items():
                db = fb.get(j)
                nd = dict(da)
                if db is not None:
                    ra, rb = da.get('rot'), db.get('rot')
                    if ra is not None and rb is not None and ra != rb:
                        nd['rot'] = _q2e(slerp(q(i, j), q(i + 1, j), a), prev.get(j, ra))
                    pa, pb = da.get('pos'), db.get('pos')
                    if pa is not None and pb is not None:
                        nd['pos'] = _lerp(pa, pb, a)
                fr[j] = nd
            for j, db in fb.items():
                if j not in fr:
                    fr[j] = dict(db)
        for j, d in fr.items():  # точные кадры копируются как есть, смешанные уже непрерывны с prev
            if 'rot' in d:
                prev[j] = d['rot']
        out.append(fr)
    return out


def _count(duration, fps):
    return max(2, int(round(duration * fps)) + 1)


def retime(frames: list, fps: float, speed: float = 1.0, target_fps=None):
    """Изменить скорость воспроизведения и/или частоту кадров. Возвращает (кадры, fps).

    speed > 1 — быстрее (клип короче, кадров меньше), < 1 — медленнее. target_fps —
    новая частота кадров (None — прежняя). Первый и последний кадр сохраняются точно,
    длительность округляется до целого числа кадров (ошибка скорости ≤ полкадра).
    """
    _check_frames(frames)
    fps = _num(fps, 'Частота кадров', positive=True)
    speed = _num(speed, 'Скорость', positive=True)
    out_fps = fps if target_fps is None else _num(target_fps, 'Новая частота кадров', positive=True)
    n = len(frames)
    if n == 1:
        return _copy(frames), out_fps
    dur = (n - 1) / fps
    m = _count(dur / speed, out_fps)
    return _resample(frames, fps, [k * dur / (m - 1) for k in range(m)]), out_fps


def speed_ramp(frames: list, fps: float, points):
    """Плавно меняющаяся скорость. points = [(время_с, скорость), ...] по времени исходного клипа.

    Между точками скорость линейна, до первой и после последней — постоянна. Время
    выхода = ∫ ds / скорость(s); затем пересэмплирование с той же fps. Первый и последний
    кадр сохраняются. Возвращает (кадры, fps).
    """
    _check_frames(frames)
    fps = _num(fps, 'Частота кадров', positive=True)
    try:
        pts = sorted((_num(t, 'Время точки'), _num(v, 'Скорость точки', positive=True)) for t, v in points)
    except (TypeError, ValueError) as e:
        if isinstance(e, ValueError) and str(e).startswith(('Время', 'Скорость')):
            raise
        raise ValueError('Точки скорости: нужен список пар (время, скорость)') from None
    if not pts:
        raise ValueError('Точки скорости: нужна хотя бы одна точка')
    n = len(frames)
    if n == 1:
        return _copy(frames), fps
    ts, vs = [p[0] for p in pts], [p[1] for p in pts]

    def speed_at(s):
        k = bisect.bisect_right(ts, s)
        if k == 0:
            return vs[0]
        if k == len(ts):
            return vs[-1]
        t0, t1 = ts[k - 1], ts[k]
        return vs[k - 1] + (vs[k] - vs[k - 1]) * (s - t0) / (t1 - t0) if t1 > t0 else vs[k]

    dur = (n - 1) / fps
    steps = (n - 1) * 8
    src = [dur * k / steps for k in range(steps + 1)]
    warp = [0.0]
    for k in range(steps):  # трапеции по 1/скорость
        warp.append(warp[-1] + (src[k + 1] - src[k]) * 0.5 * (1 / speed_at(src[k]) + 1 / speed_at(src[k + 1])))
    total = warp[-1]
    m = _count(total, fps)
    times, k = [], 0
    for i in range(m):
        t = total * i / (m - 1)
        while k < steps - 1 and warp[k + 1] < t:
            k += 1
        span = warp[k + 1] - warp[k]
        a = 0.0 if span <= 0 else min(1.0, max(0.0, (t - warp[k]) / span))
        times.append(src[k] + a * (src[k + 1] - src[k]))
    times[0], times[-1] = 0.0, dur
    return _resample(frames, fps, times), fps


# ---------------------------------------------------------------- плавный вход/выход

def _hold(root: Joint, frame: dict, pose: str, height: float) -> dict:
    if pose == 'first':
        return frame
    rest = {}
    for j, d in frame.items():
        nd = dict(d)
        if 'rot' in d:
            nd['rot'] = (0.0, 0.0, 0.0)
        rest[j] = nd
    rp = frame.get(root.name, {}).get('pos')
    if rp is not None:
        rest[root.name]['pos'] = (rp[0], height, rp[2])
    return rest


def _blend(hold, motion, w, prev):
    """hold → motion с весом w (0 — поза, 1 — движение)."""
    out = {}
    for j, dm in motion.items():
        dh = hold.get(j)
        nd = dict(dm)
        if dh is not None:
            rh, rm = dh.get('rot'), dm.get('rot')
            if rh is not None and rm is not None and rh != rm:
                nd['rot'] = _q2e(slerp(_e2q(rh), _e2q(rm), w), prev.get(j, rm))
            ph, pm = dh.get('pos'), dm.get('pos')
            if ph is not None and pm is not None:
                nd['pos'] = _lerp(ph, pm, w)
        out[j] = nd
    return out


def ease(root: Joint, frames: list, fps: float, fade_in: float = 0.0, fade_out: float = 0.0,
         pose: str = 'first') -> list:
    """Плавно начать и закончить движение из неподвижной позы.

    fade_in — сколько секунд в начале движение «разгоняется» из позы, fade_out — сколько
    секунд в конце «затухает» в позу (вес smoothstep, без скачков скорости). pose='first' —
    держим первый (в конце — последний) кадр; 'rest' — нулевые повороты, корень на высоте
    первого кадра, по горизонтали — где был в первом (последнем) кадре. Горизонтальный путь
    корня смешивается тоже: персонаж плавно трогается и плавно останавливается.
    Кадры между зонами не меняются.
    """
    if not isinstance(root, Joint):
        raise ValueError('Нужен скелет (корневой сустав)')
    _check_frames(frames)
    fps = _num(fps, 'Частота кадров', positive=True)
    fi = _num(fade_in, 'Плавный вход')
    fo = _num(fade_out, 'Плавный выход')
    if fi < 0 or fo < 0:
        raise ValueError('Длительность плавного входа/выхода не может быть отрицательной')
    if pose not in ('first', 'rest'):
        raise ValueError("Поза: 'first' (первый/последний кадр) или 'rest' (нулевые повороты)")
    n = len(frames)
    dur = (n - 1) / fps
    if fi + fo > dur + 1e-9:
        raise ValueError(f'Вход и выход ({fi:g} + {fo:g} с) длиннее клипа ({dur:g} с)')
    out = _copy(frames)
    height = frames[0].get(root.name, {}).get('pos', (0.0, 0.0, 0.0))[1]
    if fi > 0:
        hold, prev = _hold(root, frames[0], pose, height), {}
        for i in range(n):
            t = i / fps
            if t >= fi:
                break
            out[i] = _blend(hold, frames[i], _smooth(t / fi), prev)
            prev = {j: d['rot'] for j, d in out[i].items() if 'rot' in d}
    if fo > 0:
        hold, prev = _hold(root, frames[-1], pose, height), {}
        start = next(i for i in range(n) if dur - i / fps < fo)
        if start > 0:
            prev = {j: d['rot'] for j, d in out[start - 1].items() if 'rot' in d}
        for i in range(start, n):
            out[i] = _blend(hold, out[i], _smooth((dur - i / fps) / fo), prev)
            prev = {j: d['rot'] for j, d in out[i].items() if 'rot' in d}
    return out
