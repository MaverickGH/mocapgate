"""MoCapGate — чистка готового BVH-движения на stdlib (без numpy): сглаживание и фиксация стоп.

Работает с любым скелетом из core.skeleton.Joint (SMPL от GVHMR, SOMA от GEM-X, имена
с префиксом mixamorig:). Кадр: {имя: {'rot': (z, x, y) градусы, 'pos': (x, y, z) см у корня}},
повороты ZXY: R = Rz·Rx·Ry (core.rotations). Y вверх, сантиметры.

smooth — One Euro по кватернионам и позиции корня: на медленных участках гасит дрожание,
на быстрых почти не запаздывает. foot_lock — опорная стопа стоит на месте: контакт по высоте
и скорости, точка опоры = среднее положение голеностопа за контакт, ноги доводятся
аналитическим IK из двух звеньев, мировая ориентация стопы сохраняется.
foot_cleanup — когда «плывёт» всё тело (GEM-X): контакты без порога горизонтальной скорости
(или вероятности контакта от модели), plant_root перестраивает горизонталь корня так, чтобы
опорная стопа стояла, затем foot_lock доводит остаток и высоту.
"""
from __future__ import annotations
import math

from core.rotations import matrix_to_euler_zxy, continuous_euler, quat_to_matrix

_FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")
_I = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _base(name: str) -> str:
    return name.rsplit(":", 1)[-1]


# ---------------------------------------------------------------- быстрая линейная алгебра

def _euler_m(e):
    """(z, x, y) градусы → Rz·Rx·Ry в явном виде (как euler_zxy_to_matrix, но без matmul)."""
    z, x, y = math.radians(e[0]), math.radians(e[1]), math.radians(e[2])
    cz, sz, cx, sx, cy, sy = math.cos(z), math.sin(z), math.cos(x), math.sin(x), math.cos(y), math.sin(y)
    return ((cz * cy - sz * sx * sy, -sz * cx, cz * sy + sz * sx * cy),
            (sz * cy + cz * sx * sy, cz * cx, sz * sy - cz * sx * cy),
            (-cx * sy, sx, cx * cy))


def _mm(a, b):
    a0, a1, a2 = a
    b0, b1, b2 = b
    return tuple((r[0] * b0[0] + r[1] * b1[0] + r[2] * b2[0],
                  r[0] * b0[1] + r[1] * b1[1] + r[2] * b2[1],
                  r[0] * b0[2] + r[1] * b1[2] + r[2] * b2[2]) for r in (a0, a1, a2))


def _mt(a):
    return ((a[0][0], a[1][0], a[2][0]), (a[0][1], a[1][1], a[2][1]), (a[0][2], a[1][2], a[2][2]))


def _mv(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _axis_angle(axis, ang):
    """Поворот вокруг единичной оси на угол (рад)."""
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    t = 1 - c
    return ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c))


def _rot_between(a, b):
    """Кратчайший поворот направления a в направление b."""
    la, lb = _len(a), _len(b)
    if la < 1e-9 or lb < 1e-9:
        return _I
    c = _cross(a, b)
    s = _len(c)
    if s < 1e-9 * la * lb:
        return _I
    return _axis_angle((c[0] / s, c[1] / s, c[2] / s), math.atan2(s, _dot(a, b)))


def _quat(e):
    """(z, x, y) градусы → кватернион (w, x, y, z) = qz·qx·qy."""
    hz, hx, hy = math.radians(e[0]) / 2, math.radians(e[1]) / 2, math.radians(e[2]) / 2
    cz, sz, cx, sx, cy, sy = math.cos(hz), math.sin(hz), math.cos(hx), math.sin(hx), math.cos(hy), math.sin(hy)
    # qz·qx = (cz·cx, cz·sx, sz·sx, sz·cx); затем ·qy
    w, x, y, z = cz * cx, cz * sx, sz * sx, sz * cx
    return (w * cy - y * sy, x * cy - z * sy, w * sy + y * cy, z * cy + x * sy)


# ---------------------------------------------------------------- прямая кинематика

def _flat(root, keep=None):
    """Суставы в порядке обхода: (имя, индекс родителя, offset, end_offset)."""
    out = []

    def walk(j, parent):
        if keep is not None and j.name not in keep:
            return
        i = len(out)
        out.append((j.name, parent, tuple(float(v) for v in j.offset), j.end_offset))
        for c in j.children:
            walk(c, i)
    walk(root, -1)
    return out


def _fk(flat, frame):
    """Один кадр: (позиции, мировые повороты) по именам."""
    pos, rot = {}, {}
    P, G = [None] * len(flat), [None] * len(flat)
    for i, (name, p, off, _) in enumerate(flat):
        d = frame.get(name) or {}
        R = _euler_m(d.get("rot", (0.0, 0.0, 0.0)))
        if p < 0:
            G[i] = R
            P[i] = tuple(float(v) for v in d["pos"]) if "pos" in d else off
        else:
            G[i] = _mm(G[p], R)
            P[i] = _add(P[p], _mv(G[p], off))
        pos[name], rot[name] = P[i], G[i]
    return pos, rot


def world_positions(root, frames) -> list[dict]:
    """Мировые позиции суставов (см) по кадрам: [{имя: (x, y, z)}].

    Корень стоит в своей 'pos' (если её нет — в OFFSET), как в core/bvh.py и Blender.
    """
    flat = _flat(root)
    return [_fk(flat, fr)[0] for fr in frames]


# ---------------------------------------------------------------- сглаживание

class _Euro:
    """One Euro (Casiez 2012) для вектора: срез растёт с модулем скорости, без покомпонентных рывков."""

    def __init__(self, fps, min_cutoff, beta, scale=1.0, d_cutoff=1.0):
        self.dt = 1.0 / fps
        self.min_cutoff, self.beta, self.scale = min_cutoff, beta, scale
        self.a_d = self._alpha(d_cutoff)
        self.x, self.dx = None, None

    def _alpha(self, cutoff):
        return 1.0 / (1.0 + 1.0 / (2 * math.pi * cutoff * self.dt))

    def __call__(self, x):
        if self.x is None:
            self.x, self.dx = tuple(x), [0.0] * len(x)
            return self.x
        diff = [a - b for a, b in zip(x, self.x)]
        # производная фильтруется как вектор: шум со знаком гасится, модуль берём после
        self.dx = [p + self.a_d * (d / self.dt - p) for p, d in zip(self.dx, diff)]
        speed = self.scale * math.sqrt(sum(d * d for d in self.dx))
        a = self._alpha(self.min_cutoff + self.beta * speed)
        self.x = tuple(b + a * d for b, d in zip(self.x, diff))
        return self.x


def _cutoff(strength: float) -> float:
    """0 → 8 Гц (почти без эффекта), 0.5 → 2 Гц, 1 → 0.5 Гц; шкала логарифмическая."""
    return 8.0 * (1 / 16) ** max(0.0, min(1.0, strength))


def is_finger(name: str) -> bool:
    return any(f in _base(name) for f in _FINGERS)


def _two_way(series, make):
    """Фильтр вперёд и назад, среднее: фазовые задержки взаимно гасятся (клип обрабатывается целиком)."""
    f, b = make(), make()
    fw = [f(v) for v in series]
    bw = [b(v) for v in reversed(series)][::-1]
    return [tuple((p + q) / 2 for p, q in zip(x, y)) for x, y in zip(fw, bw)]


def smooth(root, frames: list[dict], fps: float, body: float = 0.0, hands: float = 0.0) -> list[dict]:
    """Сгладить дрожание на месте. body — тело и позиция корня, hands — суставы пальцев; 0..1, 0 = без изменений.

    Повороты фильтруются как единичные кватернионы (знак каждого кадра выбирается ближе к
    предыдущему — без перескока на другую полусферу), углы возвращаются непрерывными (без скачков 360°).
    One Euro идёт вперёд и назад, результаты усредняются: без запаздывания, быстрые движения
    почти не срезаются, медленные — гладкие.
    """
    if not frames or (body <= 0 and hands <= 0):
        return frames
    for name in (j[0] for j in _flat(root)):
        s = hands if is_finger(name) else body
        idx = [t for t, fr in enumerate(frames) if "rot" in (fr.get(name) or {})]
        if s <= 0 or not idx:
            continue
        qs, prev = [], None
        for t in idx:
            q = _quat(frames[t][name]["rot"])
            if prev is not None and sum(a * b for a, b in zip(prev, q)) < 0:
                q = tuple(-c for c in q)
            qs.append(q)
            prev = q
        out = _two_way(qs, lambda: _Euro(fps, _cutoff(s), beta=5, scale=2.0))
        e = None
        for t, q in zip(idx, out):
            n = math.sqrt(sum(c * c for c in q)) or 1.0
            q = tuple(c / n for c in q)
            d = frames[t][name]
            e = continuous_euler(matrix_to_euler_zxy(quat_to_matrix(q)), e if e is not None else tuple(d["rot"]))
            d["rot"] = e
    idx = [t for t, fr in enumerate(frames) if "pos" in (fr.get(root.name) or {})]
    if body > 0 and idx:
        out = _two_way([tuple(float(v) for v in frames[t][root.name]["pos"]) for t in idx],
                       lambda: _Euro(fps, _cutoff(body), beta=0.05))
        for t, p in zip(idx, out):
            frames[t][root.name]["pos"] = p
    return frames


# ---------------------------------------------------------------- фиксация стоп

def _find(root, base):
    stack = [root]
    while stack:
        j = stack.pop()
        if _base(j.name) == base:
            return j
        stack.extend(j.children)
    return None


def _path(root, name):
    """Цепочка имён от корня до сустава (включительно) или None."""
    if root.name == name:
        return [root.name]
    for c in root.children:
        p = _path(c, name)
        if p:
            return [root.name] + p
    return None


def _subtree(j):
    out, stack = [], [j]
    while stack:
        k = stack.pop()
        out.append(k)
        stack.extend(k.children)
    return out


def _legs(root):
    """{'Left'/'Right': (UpLeg, Leg, Foot, путь от корня до Foot, суставы стопы)} для найденных ног."""
    legs = {}
    for side in ("Left", "Right"):
        up, leg, foot = (_find(root, side + b) for b in ("UpLeg", "Leg", "Foot"))
        if not (up and leg and foot):
            continue
        path = _path(root, foot.name)
        if not path or up.name not in path or leg.name not in path or path.index(up.name) > path.index(leg.name):
            continue
        legs[side] = (up.name, leg.name, foot.name, path, _subtree(foot))
    return legs


def _percentile(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, max(0, int(q * (len(v) - 1))))] if v else 0.0


def _segments(flags, fill, min_len):
    """Флаги → отрезки [a, b) с заполнением коротких пропусков и отбросом коротких касаний."""
    segs, t, n = [], 0, len(flags)
    while t < n:
        if flags[t]:
            a = t
            while t < n and flags[t]:
                t += 1
            if segs and a - segs[-1][1] <= fill:
                segs[-1] = (segs[-1][0], t)
            else:
                segs.append((a, t))
        else:
            t += 1
    return [s for s in segs if s[1] - s[0] >= min_len]


def _contacts(low_h, ank, fps, floor, hin, hout, vin, vout):
    """Гистерезис по высоте над полом и горизонтальной скорости голеностопа (см/с)."""
    n = len(ank)
    k = max(1, round(0.04 * fps))
    flags, on = [], False
    for t in range(n):
        a, b = ank[max(0, t - k)], ank[min(n - 1, t + k)]
        span = (min(n - 1, t + k) - max(0, t - k)) or 1
        v = math.hypot(b[0] - a[0], b[2] - a[2]) * fps / span
        h = low_h[t] - floor
        on = (h < hout and v < vout) if on else (h < hin and v < vin)
        flags.append(on)
    return _segments(flags, max(1, round(0.05 * fps)), max(2, round(0.1 * fps)))


def _slide(ank, segs):
    """Наибольшее горизонтальное отклонение голеностопа от среднего положения за контакт, см."""
    worst = 0.0
    for a, b in segs:
        mx = sum(ank[t][0] for t in range(a, b)) / (b - a)
        mz = sum(ank[t][2] for t in range(a, b)) / (b - a)
        worst = max([worst] + [math.hypot(ank[t][0] - mx, ank[t][2] - mz) for t in range(a, b)])
    return worst


def _smoothstep(k):
    return k * k * (3 - 2 * k)


def _analyse(root, frames, legs, floor):
    """FK ног по кадрам, нижняя точка каждой стопы и высота пола: (flat, fks, low, floor)."""
    keep = set()
    for up, leg, foot, path, sub in legs.values():
        keep.update(path)
        keep.update(j.name for j in sub)
    flat = _flat(root, keep)
    fks = [_fk(flat, fr) for fr in frames]
    # нижняя точка стопы: голеностоп, носки и концы (End Site) — работает и без носков
    low = {}
    for side, (up, leg, foot, path, sub) in legs.items():
        hs = []
        for pos, rot in fks:
            ys = [pos[j.name][1] for j in sub]
            ys += [pos[j.name][1] + _mv(rot[j.name], j.end_offset)[1] for j in sub if j.end_offset is not None]
            hs.append(min(ys))
        low[side] = hs
    if floor is None:
        floor = _percentile([h for hs in low.values() for h in hs], 0.05)
    return flat, fks, low, floor


def detect_contacts(root, frames: list[dict], fps: float, floor: float | None = None,
                    height: float = 5.0, speed: float = 30.0) -> dict:
    """Автоматические контакты стоп ровно как в foot_lock: {'Left': [[a, b], ...], 'Right': [...]}.

    Кадры с 0, оба конца включительно; тот же гистерезис, мост через короткие пропуски и
    минимальная длительность. Сторона без найденной ноги в скелете — пустой список.
    """
    out = {"Left": [], "Right": []}
    legs = _legs(root)
    if not frames or not legs:
        return out
    _, fks, low, floor = _analyse(root, frames, legs, floor)
    for side, (up, leg, foot, path, sub) in legs.items():
        ank = [pos[foot] for pos, _ in fks]
        segs = _contacts(low[side], ank, fps, floor, height, height * 1.6, speed, speed * 2.0)
        out[side] = [[a, b - 1] for a, b in segs]
    return out


def _ranges(value, what, n):
    """{сторона: [[a, b], ...]} → {сторона: [(a, b+1), ...]} с проверкой; n=None — без верхней границы."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{what}: нужен объект {{'Left': [[a, b], ...], 'Right': [...]}}")
    out = {}
    for side, ranges in value.items():
        if side not in ("Left", "Right"):
            raise ValueError(f"{what}: неизвестная сторона {side!r} (нужно Left или Right)")
        if not isinstance(ranges, (list, tuple)):
            raise ValueError(f"{what} ({side}): нужен список отрезков [[a, b], ...]")
        segs = []
        for r in ranges:
            if not isinstance(r, (list, tuple)) or len(r) != 2 or any(
                    isinstance(v, bool) or not isinstance(v, int) for v in r):
                raise ValueError(f"{what} ({side}): отрезок {r!r} должен быть парой целых кадров [a, b]")
            a, b = r
            if a < 0 or b < a or (n is not None and b >= n):
                lim = f"кадры 0..{n - 1}, " if n is not None else ""
                raise ValueError(f"{what} ({side}): отрезок [{a}, {b}] вне клипа или перевёрнут ({lim}a ≤ b)")
            segs.append((a, b + 1))
        out[side] = segs
    return out


def _union(segs):
    """Объединение полуинтервалов; соседние (без пропуска) сливаются."""
    merged = []
    for a, b in sorted(segs):
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def merge_contacts(auto, add=None, remove=None, frames=None) -> dict:
    """Ручная правка поверх автоконтактов: (auto ∪ add) \\ remove → {'Left': [[a, b], ...], 'Right': [...]}.

    Все отрезки — кадры с 0, оба конца включительно. Пересекающиеся и соседние отрезки сливаются,
    удаление режет отрезки на части, пустые остатки отбрасываются. frames — число кадров
    (или сам список кадров): тогда отрезки за пределами клипа — ValueError. Всегда возвращает
    обе стороны, так что результат можно отдать в foot_lock(contacts=...) целиком.
    """
    n = len(frames) if isinstance(frames, (list, tuple)) else frames
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 0):
        raise ValueError("Контакты стоп: frames — число кадров или список кадров")
    A = _ranges(auto, "Автоконтакты", n)
    P = _ranges(add, "Добавленные контакты", n)
    M = _ranges(remove, "Убранные контакты", n)
    out = {}
    for side in ("Left", "Right"):
        segs = _union(A.get(side, []) + P.get(side, []))
        for ra, rb in _union(M.get(side, [])):
            cut = []
            for a, b in segs:
                if rb <= a or ra >= b:
                    cut.append((a, b))
                    continue
                if a < ra:
                    cut.append((a, ra))
                if rb < b:
                    cut.append((rb, b))
            segs = cut
        out[side] = [[a, b - 1] for a, b in segs if b - a >= 1]
    return out


def _manual_contacts(contacts, n):
    """Проверить ручные контакты → {сторона: [(a, b+1), ...]} (полуинтервалы, отсортированы, слиты)."""
    out = {}
    for side, segs in _ranges(contacts, "Контакты стоп", n).items():
        merged = []
        for a, b in sorted(segs):  # сливаются только пересечения: соседние отрезки — разные точки опоры
            if merged and a < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        out[side] = merged
    return out


def foot_lock(root, frames: list[dict], fps: float, strength: float = 1.0, floor: float | None = None,
              height: float = 5.0, speed: float = 30.0, max_drop: float = 3.0, contacts: dict | None = None):
    """Убрать скольжение опорных стоп на месте. Возвращает (frames, report).

    strength 0..1 — доля коррекции (0 — без изменений); floor — высота пола (см), по умолчанию
    5-й перцентиль нижней точки стоп; height/speed — порог входа в контакт (см над полом, см/с),
    выход — при высоте 1.6× и скорости 2× от них (гистерезис); max_drop — насколько можно опустить таз (см), если при
    двух опорах нога не дотягивается. contacts — ручные контакты {'Left': [[a, b], ...], 'Right': [...]},
    кадры с 0 включительно: для указанной стороны автоопределение заменяется ровно этими отрезками
    (пустой список — стопа не фиксируется), отсутствующие стороны определяются автоматически.
    Меняются только UpLeg/Leg/Foot (и Y корня при опускании таза).
    report: contacts {'Left': n, 'Right': n}, slide_before/slide_after {'Left': см, ...}, max_drop см.
    """
    report = {"contacts": {}, "slide_before": {}, "slide_after": {}, "max_drop": 0.0}
    legs = _legs(root)
    n = len(frames)
    manual = _manual_contacts(contacts, n)
    if not frames or not legs:
        return frames, report
    flat, fks, low, floor = _analyse(root, frames, legs, floor)
    ramp = max(1, round(0.1 * fps))
    weights, pins, segs_by = {}, {}, {}
    for side, (up, leg, foot, path, sub) in legs.items():
        ank = [pos[foot] for pos, _ in fks]
        if side in manual:
            segs = manual[side]
        else:
            segs = _contacts(low[side], ank, fps, floor, height, height * 1.6, speed, speed * 2.0)
        segs_by[side] = segs
        report["contacts"][side] = len(segs)
        report["slide_before"][side] = round(_slide(ank, segs), 3)
        w, pin = [0.0] * n, [None] * n
        for a, b in segs:
            p = tuple(sum(ank[t][i] for t in range(a, b)) / (b - a) for i in range(3))
            for t in range(max(0, a - ramp), min(n, b + ramp)):
                k = 1.0 if a <= t < b else _smoothstep(1 - ((a - t) if t < a else (t - b + 1)) / (ramp + 1))
                if k > w[t]:
                    w[t], pin[t] = k, p
        weights[side] = [x * max(0.0, min(1.0, strength)) for x in w]
        pins[side] = pin

    def target(side, t, pos):
        w, p = weights[side][t], pins[side][t]
        a = pos[legs[side][2]]
        return (a[0] + w * (p[0] - a[0]), a[1] + w * (p[1] - a[1]), a[2] + w * (p[2] - a[2]))

    # опускание таза: только когда обе стопы зафиксированы и цель вне досягаемости
    drops = [0.0] * n
    if len(legs) == 2 and max_drop > 0 and root.name in frames[0] and "pos" in frames[0][root.name]:
        for t, (pos, _) in enumerate(fks):
            if not all(weights[s][t] > 0 for s in legs):
                continue
            for side, (up, leg, foot, path, sub) in legs.items():
                hip, T = pos[up], target(side, t, pos)
                L = (_len(_sub(pos[leg], hip)) + _len(_sub(pos[foot], pos[leg]))) * 0.995
                h2 = (T[0] - hip[0]) ** 2 + (T[2] - hip[2]) ** 2
                need = hip[1] - T[1] - math.sqrt(L * L - h2) if L * L > h2 else max_drop
                drops[t] = max(drops[t], min(max_drop, max(0.0, need)) * min(weights[s][t] for s in legs))
        if any(drops):
            r = ramp
            mx = [max(drops[max(0, t - r):t + r + 1]) for t in range(n)]  # без провалов, затем плавно
            drops = [sum(mx[max(0, t - r):t + r + 1]) / len(mx[max(0, t - r):t + r + 1]) for t in range(n)]
            report["max_drop"] = round(max(drops), 3)
    for t, fr in enumerate(frames):
        pos, rot = fks[t]
        dy = drops[t]
        if dy > 0:
            x, y, z = fr[root.name]["pos"]
            fr[root.name]["pos"] = (x, y - dy, z)
        for side, (up, leg, foot, path, sub) in legs.items():
            if weights[side][t] <= 0:
                continue
            T = target(side, t, pos)
            shift = (0.0, -dy, 0.0)
            hip, knee, ank = _add(pos[up], shift), _add(pos[leg], shift), _add(pos[foot], shift)
            _solve_leg(fr, rot, path, up, leg, foot, hip, knee, ank, T)
    after = [_fk(flat, fr)[0] for fr in frames]
    for side in legs:
        report["slide_after"][side] = round(_slide([p[legs[side][2]] for p in after], segs_by[side]), 3)
    return frames, report


def _solve_leg(fr, rot, path, up, leg, foot, hip, knee, ank, T, pole=None):
    """Аналитический IK бедро→колено→стопа; плоскость колена сохраняется (или проходит через pole —
    мировую точку, куда должно смотреть колено), ориентация стопы в мире — тоже."""
    u, v = _sub(hip, knee), _sub(ank, knee)
    la, lb = _len(u), _len(v)
    if la < 1e-6 or lb < 1e-6:
        return
    d = min(max(_len(_sub(T, hip)), abs(la - lb) + 1e-3), la + lb - 1e-4)
    cur = math.acos(max(-1.0, min(1.0, _dot(u, v) / (la * lb))))
    new = math.acos(max(-1.0, min(1.0, (la * la + lb * lb - d * d) / (2 * la * lb))))
    nrm = _cross(u, v)
    ln = _len(nrm)
    if ln < 1e-6 * la * lb:  # прямая нога: ось сгиба — минус локальная X голени (колено вперёд)
        g = rot[leg]
        nrm, ln = (-g[0][0], -g[1][0], -g[2][0]), 1.0
    dK = _axis_angle((nrm[0] / ln, nrm[1] / ln, nrm[2] / ln), new - cur)
    a1 = _add(knee, _mv(dK, v))
    dH = _rot_between(_sub(a1, hip), _sub(T, hip))
    # вернуть колено в исходную плоскость: поворот вокруг оси бедро→цель
    e = _sub(T, hip)
    le = _len(e)
    if le > 1e-6:
        e = (e[0] / le, e[1] / le, e[2] / le)
        k2 = _mv(dH, _sub(knee, hip))
        k0 = _sub(pole if pole is not None else knee, hip)
        p2 = _sub(k2, tuple(c * _dot(k2, e) for c in e))
        p0 = _sub(k0, tuple(c * _dot(k0, e) for c in e))
        if _len(p2) > 1e-6 and _len(p0) > 1e-6:
            ang = math.atan2(_dot(_cross(p2, p0), e), _dot(p2, p0))
            dH = _mm(_axis_angle(e, ang), dH)
    gp = lambda name: rot[path[path.index(name) - 1]] if path.index(name) > 0 else _I
    updates = {
        up: _mm(_mt(gp(up)), _mm(dH, rot[up])),
        leg: _mm(_mt(gp(leg)), _mm(dK, rot[leg])),
        foot: _mm(_mt(gp(foot)), _mm(_mt(dK), _mm(_mt(dH), rot[foot]))),
    }
    for name, m in updates.items():
        d = fr.setdefault(name, {})
        d["rot"] = continuous_euler(matrix_to_euler_zxy(m), tuple(d.get("rot", (0.0, 0.0, 0.0))))


# ---------------------------------------------------------------- скольжение всего тела: корень + стопы

def resample_series(values, source_fps: float, target_fps: float, n: int) -> list:
    """Покадровый ряд чисел (None = 0) из частоты source_fps в n кадров target_fps, линейно (как resample_person)."""
    vals = [float(v) if v is not None else 0.0 for v in (values or [])]
    if not vals or n <= 0:
        return [0.0] * max(0, n)
    count, out = len(vals), []
    for i in range(n):
        p = min(count - 1, i * float(source_fps) / float(target_fps))
        a = int(p)
        b = min(count - 1, a + 1)
        out.append(vals[a] + (vals[b] - vals[a]) * (p - a))
    return out


def contacts_from_probabilities(probs, fps: float, on: float = 0.5, off: float = 0.3) -> list:
    """Вероятности контакта по кадрам (None = 0) → отрезки [[a, b], ...] (оба конца включительно).

    Гистерезис: вход при p ≥ on, выход при p < off; короткие пропуски (≤ 0.05 с) заполняются,
    касания короче 0.1 с отбрасываются — как у автоопределения.
    """
    flags, state = [], False
    for p in probs or []:
        p = 0.0 if p is None else float(p)
        state = p >= off if state else p >= on
        flags.append(state)
    return [[a, b - 1] for a, b in _segments(flags, max(1, round(0.05 * fps)), max(2, round(0.1 * fps)))]


def _contacts_robust(low_h, other_h, ank, fps, floor, hin, hout, vy_in, vy_out, lower, max_speed):
    """Контакт без порога горизонтальной скорости: стопа у пола, она ниже другой (или обе у пола),
    почти не движется по вертикали. Скользящая опорная стопа так тоже находится."""
    n = len(low_h)
    k = max(1, round(0.04 * fps))
    flags, on = [], False
    for t in range(n):
        a, b = max(0, t - k), min(n - 1, t + k)
        span = (b - a) or 1
        vy = abs(low_h[b] - low_h[a]) * fps / span
        v = math.hypot(ank[b][0] - ank[a][0], ank[b][2] - ank[a][2]) * fps / span
        h = low_h[t] - floor
        o = other_h[t] - floor if other_h is not None else h
        if on:
            on = h < hout and vy < vy_out and v < max_speed * 1.3 and (h <= o + 2 * lower or o < hout)
        else:
            on = h < hin and vy < vy_in and v < max_speed and (h <= o + lower or o < hin)
        flags.append(on)
    return _segments(flags, max(1, round(0.05 * fps)), max(2, round(0.1 * fps)))


def detect_contacts_robust(root, frames: list[dict], fps: float, floor: float | None = None, height: float = 5.0,
                           vertical: float = 15.0, lower: float = 3.0, max_speed: float = 150.0) -> dict:
    """Контакты стоп, устойчивые к скольжению: {'Left': [[a, b], ...], 'Right': [...]} (включительно).

    Вход: нижняя точка стопы ниже height см над полом, вертикальная скорость < vertical см/с,
    стопа не выше другой более чем на lower см (или обе у пола) и горизонтальная скорость < max_speed
    (отсекает только явный мах ногой). Выход — при 1.6× высоте, 2× вертикальной скорости.
    """
    out = {"Left": [], "Right": []}
    legs = _legs(root)
    if not frames or not legs:
        return out
    _, fks, low, floor = _analyse(root, frames, legs, floor)
    for side, (up, leg, foot, path, sub) in legs.items():
        other = low.get("Right" if side == "Left" else "Left")
        ank = [pos[foot] for pos, _ in fks]
        segs = _contacts_robust(low[side], other, ank, fps, floor, height, height * 1.6,
                                vertical, vertical * 2.0, lower, max_speed)
        out[side] = [[a, b - 1] for a, b in segs]
    return out


def _taper(segs, n, ramp):
    """Отрезки [a, b) → вес 0..1 по кадрам: внутри контакта плавный вход/выход за ramp кадров (наружу не выходит)."""
    w = [0.0] * n
    for a, b in segs:
        for t in range(max(0, a), min(n, b)):
            k = min(t - a + 1, b - t) / (ramp + 1)
            w[t] = max(w[t], _smoothstep(min(1.0, k)))
    return w


def plant_root(root, frames: list[dict], fps: float, contacts: dict, strength: float = 1.0,
               max_shift: float = 300.0, release: float = 0.5):
    """Опорная стопа не едет, даже если «плывёт» всё тело: горизонталь корня перестраивается. Возвращает (frames, report).

    contacts — {'Left': [[a, b], ...], 'Right': [...]} (кадры с 0, включительно). Скорость корня по X/Z
    = исходная скорость минус горизонтальная скорость опорной стопы (голеностопа); при двух опорах —
    взвешенно по весам контакта. Веса плавно входят и выходят внутри контакта (≈0.06 с), поэтому
    корень не дёргается при смене опоры. Y корня не меняется, повороты не меняются.
    Сдвиг от траектории видео не копится без предела: без опоры (полёт, прыжок) он возвращается к видео
    за ≈release с, а дальше max_shift см коррекция ослабевает — иначе на длинном клипе человек
    уезжает от своего места в кадре и от других участников.
    report: slide_before / slide_after {'Left': см, ...}, max_shift — наибольший сдвиг корня, см.
    """
    report = {"slide_before": {}, "slide_after": {}, "max_shift": 0.0}
    legs = _legs(root)
    n = len(frames)
    if not frames or not legs or "pos" not in (frames[0].get(root.name) or {}):
        return frames, report
    segs = _manual_contacts(contacts, n)
    _, fks, _, _ = _analyse(root, frames, legs, 0.0)
    ramp = max(1, round(0.06 * fps))
    s = max(0.0, min(1.0, strength))
    ank = {side: [pos[legs[side][2]] for pos, _ in fks] for side in legs}
    weight = {side: _taper(segs.get(side, []), n, ramp) for side in legs}
    off, offs = (0.0, 0.0), [(0.0, 0.0)]
    for t in range(1, n):
        e = {side: min(weight[side][t - 1], weight[side][t]) for side in legs}
        total = sum(e.values())
        dx = dz = 0.0
        if total > 0:
            k = max(e.values()) * s * max(0.0, min(1.0, 2.0 - math.hypot(*off) / max_shift))
            for side, w in e.items():
                if w > 0:
                    a, b = ank[side][t - 1], ank[side][t]
                    dx += k * w / total * (b[0] - a[0])
                    dz += k * w / total * (b[2] - a[2])
        off = (off[0] - dx, off[1] - dz)
        if total <= 0 and release > 0:
            keep = math.exp(-1.0 / (release * fps))
            off = (off[0] * keep, off[1] * keep)
        offs.append(off)
    for t, fr in enumerate(frames):
        x, y, z = fr[root.name]["pos"]
        fr[root.name]["pos"] = (x + offs[t][0], y, z + offs[t][1])
    report["max_shift"] = round(max(math.hypot(*o) for o in offs), 3)
    for side in legs:
        ss = segs.get(side, [])
        report["slide_before"][side] = round(_slide(ank[side], ss), 3)
        moved = [(p[0] + o[0], p[1], p[2] + o[1]) for p, o in zip(ank[side], offs)]
        report["slide_after"][side] = round(_slide(moved, ss), 3)
    return frames, report


def _is_probabilities(value):
    return isinstance(value, (list, tuple)) and all(
        v is None or (isinstance(v, (int, float)) and not isinstance(v, bool)) for v in value) and bool(value)


def foot_cleanup(root, frames: list[dict], fps: float, contacts: dict | None = None, strength: float = 1.0,
                 floor: float | None = None, max_drop: float = 3.0, threshold: float = 0.5):
    """Полная чистка стоп: контакты → plant_root (корень) → foot_lock (IK ног, высота). Возвращает (frames, report).

    contacts по сторонам 'Left'/'Right' (отсутствующая сторона — автоопределение detect_contacts_robust):
    список вероятностей по кадрам (None = 0; например static_conf модели GEM-X, уже в частоте кадров
    клипа) — контакт по порогу threshold с гистерезисом; или отрезки [[a, b], ...] — ровно они.
    report: contacts {'Left': n, ...}, slide_before (исходный клип) / slide_after (итог) {'Left': см},
    max_drop, root_shift см, source {'Left': 'model'|'manual'|'auto'}, step_after {'Left': см за кадр в контакте}.
    """
    report = {"contacts": {}, "slide_before": {}, "slide_after": {}, "max_drop": 0.0, "root_shift": 0.0, "source": {}}
    legs = _legs(root)
    n = len(frames)
    if not frames or not legs:
        return frames, report
    given = contacts or {}
    if not isinstance(given, dict):
        raise ValueError("Контакты стоп: нужен объект {'Left': ..., 'Right': ...}")
    auto = None
    segs = {}
    for side in ("Left", "Right"):
        value = given.get(side)
        if _is_probabilities(value):
            probs = list(value)[:n] + [0.0] * max(0, n - len(value))
            segs[side] = contacts_from_probabilities(probs, fps, threshold, threshold * 0.6)
            report["source"][side] = "model"
        elif value is not None:
            segs[side] = [list(r) for r in value]
            report["source"][side] = "manual"
        else:
            if auto is None:
                auto = detect_contacts_robust(root, frames, fps, floor)
            segs[side] = auto[side]
            report["source"][side] = "auto"
    _manual_contacts(segs, n)  # проверка отрезков до изменений
    frames, planted = plant_root(root, frames, fps, segs, strength)
    frames, locked = foot_lock(root, frames, fps, strength=strength, floor=floor, max_drop=max_drop,
                               contacts={s: v for s, v in segs.items() if s in legs})
    report["contacts"] = locked["contacts"]
    report["slide_before"] = planted["slide_before"] or locked["slide_before"]
    report["slide_after"] = locked["slide_after"]
    report["max_drop"] = locked["max_drop"]
    report["root_shift"] = planted["max_shift"]
    report["step_after"] = {s: v["per_frame_cm"] for s, v in contact_slide(root, frames, segs).items()}
    return frames, report


# ---------------------------------------------------------------- ретаргет ног на исходные суставы модели

def resample_points(frames, source_fps: float, target_fps: float, n: int) -> list:
    """Кадры точек [[x, y, z], ...] (None — нет данных) из source_fps в n кадров target_fps, линейно."""
    frames = list(frames or [])
    if not frames or n <= 0:
        return [None] * max(0, n)
    count, out = len(frames), []
    for i in range(n):
        p = min(count - 1, i * float(source_fps) / float(target_fps))
        a = int(p)
        b = min(count - 1, a + 1)
        u = p - a
        A, B = frames[a], frames[b]
        if A is None or B is None:
            out.append(A if u < 0.5 else B)
            continue
        out.append([[x + (y - x) * u for x, y in zip(pa, pb)] for pa, pb in zip(A, B)])
    return out


def retarget_legs(root, frames: list[dict], source: dict, floor: float = 0.0, max_drop: float = 15.0):
    """Ноги BVH точно в суставы исходной модели по кадрам: стопа (голеностоп) в исходной точке. Возвращает (frames, report).

    source — {'names': [...], 'positions': [[[x, y, z], ...] по кадрам]} в см, в системе клипа; нужны
    <Side>UpLeg, <Side>Leg (колено), <Side>Foot (голеностоп). Это ретаргет на скелет с постоянными
    длинами костей (BVH) из скелета модели, у которого длины могут отличаться от кадра к кадру:
    1) высота корня над полом (floor, см) умножается на отношение длины ноги BVH к исходной в этом кадре
       (ноги исходника на 10 % длиннее — таз ниже на столько же, сгиб колена сохраняется);
       если цель всё ещё недостижима, корень опускается ровно настолько, насколько нужно (≤ max_drop см);
    2) аналитический IK из двух звеньев: голеностоп — в исходный голеностоп, колено — в плоскости исходного
       колена (pole), ориентация стопы в мире (и носка) сохраняется. X/Z корня не меняются.
    report: frames, error_before / error_after {'max': см, 'mean': см} по голеностопам, toe_error_after (если
    есть носки), max_drop см, ratio {'min', 'max'}.
    """
    report = {"frames": 0, "error_before": {"max": 0.0, "mean": 0.0}, "error_after": {"max": 0.0, "mean": 0.0},
              "toe_error_after": None, "max_drop": 0.0, "ratio": {"min": 1.0, "max": 1.0}}
    legs = _legs(root)
    names = [_base(n) for n in (source or {}).get("names", [])]
    positions = (source or {}).get("positions") or []
    index = {n: i for i, n in enumerate(names)}
    sides = [s for s in legs if all(s + b in index for b in ("UpLeg", "Leg", "Foot"))]
    if not frames or not sides or "pos" not in (frames[0].get(root.name) or {}):
        return frames, report
    joints = {j.name: j for j in _subtree(root)}
    toes = {}
    for s in sides:
        foot = joints[legs[s][2]]
        for child in foot.children:
            if _base(child.name) in index:
                toes[s] = (child.name, index[_base(child.name)])
                break
    keep = set()
    for s in sides:
        keep.update(legs[s][3])
        keep.update(j.name for j in legs[s][4])
    flat = _flat(root, keep)
    target_len = {s: _len(joints[legs[s][1]].offset) + _len(joints[legs[s][2]].offset) for s in sides}
    before, after, toe_err, ratios = [], [], [], []

    def err(pos, S):
        return [_len(_sub(pos[legs[s][2]], tuple(S[index[s + "Foot"]]))) for s in sides]

    for t, fr in enumerate(frames):
        S = positions[t] if t < len(positions) else None
        if not S:
            continue
        pos, rot = _fk(flat, fr)
        before += err(pos, S)
        src_len = sum(_len(_sub(tuple(S[index[s + "UpLeg"]]), tuple(S[index[s + "Leg"]])))
                      + _len(_sub(tuple(S[index[s + "Leg"]]), tuple(S[index[s + "Foot"]]))) for s in sides)
        r = sum(target_len.values()) / src_len if src_len > 1e-6 else 1.0
        ratios.append(r)
        x, y, z = fr[root.name]["pos"]
        dy = (floor + (y - floor) * r) - y
        need = 0.0
        for s in sides:
            up, leg, foot = legs[s][:3]
            hip, T = pos[up], tuple(S[index[s + "Foot"]])
            L = target_len[s] * 0.9995
            h2 = (T[0] - hip[0]) ** 2 + (T[2] - hip[2]) ** 2
            reach = hip[1] + dy - T[1]
            need = max(need, reach - math.sqrt(L * L - h2) if L * L > h2 else max_drop)
        drop = min(max_drop, max(0.0, need))
        report["max_drop"] = max(report["max_drop"], round(drop, 3))
        dy -= drop
        fr[root.name]["pos"] = (x, y + dy, z)
        shift = (0.0, dy, 0.0)
        for s in sides:
            up, leg, foot, path, _ = legs[s]
            _solve_leg(fr, rot, path, up, leg, foot, _add(pos[up], shift), _add(pos[leg], shift),
                       _add(pos[foot], shift), tuple(S[index[s + "Foot"]]), pole=tuple(S[index[s + "Leg"]]))
        pos2, _ = _fk(flat, fr)
        after += err(pos2, S)
        toe_err += [_len(_sub(pos2[toes[s][0]], tuple(S[toes[s][1]]))) for s in toes]
        report["frames"] += 1
    if before:
        report["error_before"] = {"max": round(max(before), 3), "mean": round(sum(before) / len(before), 3)}
        report["error_after"] = {"max": round(max(after), 3), "mean": round(sum(after) / len(after), 3)}
        report["ratio"] = {"min": round(min(ratios), 4), "max": round(max(ratios), 4)}
    if toe_err:
        report["toe_error_after"] = {"max": round(max(toe_err), 3), "mean": round(sum(toe_err) / len(toe_err), 3)}
    return frames, report


def contact_slide(root, frames: list[dict], contacts: dict) -> dict:
    """Скольжение голеностопа в контакте: {'Left': {'max_cm', 'per_frame_cm'}, ...} (per_frame — наибольший шаг за кадр)."""
    legs = _legs(root)
    out = {}
    if not frames or not legs:
        return out
    _, fks, _, _ = _analyse(root, frames, legs, 0.0)
    segs = _manual_contacts(contacts, len(frames))
    for side in legs:
        ank = [pos[legs[side][2]] for pos, _ in fks]
        ss = segs.get(side, [])
        step = max([0.0] + [math.hypot(ank[t][0] - ank[t - 1][0], ank[t][2] - ank[t - 1][2])
                            for a, b in ss for t in range(a + 1, b)])
        out[side] = {"max_cm": round(_slide(ank, ss), 3), "per_frame_cm": round(step, 3)}
    return out


def final_motion_metrics(root, frames: list[dict], fps: float) -> dict:
    """Measure foot support and drift on the final exported skeleton, independently of model fit."""
    if not frames or not math.isfinite(float(fps)) or fps <= 0:
        raise ValueError("fps must be positive and frames must not be empty")
    detected = detect_contacts_robust(root, frames, fps)
    drift = contact_slide(root, frames, detected)
    output = {}
    for side in ("Left", "Right"):
        spans = detected.get(side, [])
        samples = sum(max(0, int(last) - int(first) + 1) for first, last in spans)
        output[side] = {
            "intervals": len(spans),
            "contact_frames": samples,
            "coverage": round(samples / len(frames), 4),
            "max_drift_cm": drift.get(side, {}).get("max_cm") if samples >= 2 else None,
            "max_step_cm": drift.get(side, {}).get("per_frame_cm") if samples >= 2 else None,
        }
    return {"kind": "post-processed-bvh", "frames": len(frames), "fps": float(fps),
            "contacts": output, "contact_detector": "robust-kinematic"}
