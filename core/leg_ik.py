"""MoCapGate — ноги при переносе на свой персонаж: двухзвенный IK, опоры стоп, их фиксация.

Pure python (no numpy, no bpy): used by core/blender_retarget.py inside Blender and tested with
the system python. Points and vectors are (x, y, z) tuples, Z up, metres; frames are 0-based,
contact spans (a, b) include both ends.

    two_bone_ik   thigh→shin: knee and ankle for a target ankle, knee in the plane of the pole
    hip_drop      how much the hips must go down so a target becomes reachable
    frame_rotation  world rotation that carries one bone frame (axis + bend normal) onto another
    detect_contacts  flat-foot contacts: ankle and toe low and slow, hysteresis, minimum duration
    contact_weights  1 on a contact, cosine fall-off over the blend frames, 0 in the swing
    lock_contacts    one fixed point per contact (mean of the span), cosine blend in/out
    foot_slide       mean horizontal path of the foot per contact (the number to minimise)
"""
from __future__ import annotations

import math

EPS = 1e-9


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    n = length(a)
    return scale(a, 1.0 / n) if n > EPS else (0.0, 0.0, 0.0)


def lerp(a, b, t):
    return add(a, scale(sub(b, a), t))


def perpendicular(v, axis):
    """Component of v perpendicular to axis (axis need not be unit)."""
    n = dot(axis, axis)
    return v if n < EPS else sub(v, scale(axis, dot(v, axis) / n))


def two_bone_ik(root, len_a, len_b, target, pole, reach=0.999):
    """Двухзвенный IK по теореме косинусов → (knee, ankle, reached).

    d = |target − root| is clamped to [|a − b|, reach·(a + b)] (no hyperextension, no folding through);
    the ankle goes to root + d·û, the knee to root + a·cosα·û + a·sinα·v̂ with
    cosα = (a² + d² − b²) / (2ad) and v̂ the pole direction made perpendicular to û, so the knee stays in
    the plane (root, target, pole). reached is False when the target had to be clamped."""
    axis = sub(target, root)
    dist = length(axis)
    u = normalize(axis) if dist > EPS else (0.0, 0.0, -1.0)
    lo, hi = abs(len_a - len_b) + 1e-6, reach * (len_a + len_b)
    d = min(max(dist, lo), hi)
    v = normalize(perpendicular(pole, u))
    if length(v) < 0.5:  # pole along the leg: any perpendicular, the caller passes a better pole next time
        v = normalize(perpendicular((1.0, 0.0, 0.0) if abs(u[0]) < 0.9 else (0.0, 1.0, 0.0), u))
    cos_a = max(-1.0, min(1.0, (len_a * len_a + d * d - len_b * len_b) / (2 * len_a * d)))
    knee = add(root, add(scale(u, len_a * cos_a), scale(v, len_a * math.sqrt(1 - cos_a * cos_a))))
    return knee, add(root, scale(u, d)), lo - 1e-9 <= dist <= hi + 1e-9


def hip_drop(root, target, limit):
    """Насколько опустить таз (≥ 0, вдоль −Z), чтобы |target − root| ≤ limit; если цель дальше limit по
    горизонтали, опускает до высоты цели (дальше помогает только зажим в two_bone_ik)."""
    dx, dy, dz = sub(target, root)
    if dx * dx + dy * dy + dz * dz <= limit * limit:
        return 0.0
    horiz = dx * dx + dy * dy
    if horiz >= limit * limit:
        return max(0.0, -dz)
    return max(0.0, -dz - math.sqrt(limit * limit - horiz))


def smooth_max(values, radius):
    """Скользящий максимум, затем скользящее среднее того же радиуса: результат ≥ исходного в каждом кадре
    (каждое окно среднего содержит этот кадр) и без ступенек — для опускания таза."""
    n = len(values)
    if radius <= 0 or n == 0:
        return list(values)
    peak = [max(values[max(0, i - radius):i + radius + 1]) for i in range(n)]
    return [sum(peak[max(0, i - radius):i + radius + 1]) / len(peak[max(0, i - radius):i + radius + 1])
            for i in range(n)]


def _basis(u, n):
    x = normalize(u)
    y = normalize(perpendicular(n, x))
    return x, y, cross(x, y)


def frame_rotation(u0, n0, u1, n1):
    """Поворот 3×3 (строки) R = B1·B0ᵀ, где B = (û, n̂⊥, û×n̂⊥): переводит направление кости u0 точно в u1 и
    нормаль плоскости сгиба n0 в n1 — колено остаётся в плоскости, кость не прокручивается лишний раз."""
    a, b = _basis(u0, n0), _basis(u1, n1)
    return tuple(tuple(sum(b[k][i] * a[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def mat_vec(m, v):
    return tuple(dot(row, v) for row in m)


def percentile(values, q):
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * q
    i = int(k)
    return s[i] if i + 1 >= len(s) else s[i] + (s[i + 1] - s[i]) * (k - i)


def speeds(points, fps):
    """Скорость точки (м/с): центральные разности, затем среднее по 3 кадрам против дрожи."""
    n = len(points)
    if n < 2:
        return [0.0] * n
    raw = [length(sub(points[min(n - 1, i + 1)], points[max(0, i - 1)])) * fps / (min(n - 1, i + 1) - max(0, i - 1))
           for i in range(n)]
    return [sum(raw[max(0, i - 1):i + 2]) / len(raw[max(0, i - 1):i + 2]) for i in range(n)]


def detect_contacts(ankle, toe, fps, h_on=0.03, h_off=0.05, v_on=0.30, v_off=0.50, min_time=0.10,
                    max_gap=0.05):
    """Опоры стопы (вся стопа на полу) → [(a, b), ...].

    Height of each point is measured above its own floor level (5th percentile over the clip, so a rest
    pose that differs from the clip does not matter); h = max(ankle, toe), v = max of their speeds.
    A contact starts when h < h_on and v < v_on and lasts while h < h_off and v < v_off (hysteresis);
    gaps up to max_gap seconds are bridged, spans shorter than min_time seconds are dropped."""
    n = len(ankle)
    pts = [ankle] + ([toe] if toe else [])
    heights = [[p[2] for p in seq] for seq in pts]
    base = [percentile(h, 0.05) for h in heights]
    h = [max(heights[k][i] - base[k] for k in range(len(pts))) for i in range(n)]
    vel = [speeds(seq, fps) for seq in pts]
    v = [max(vs[i] for vs in vel) for i in range(n)]
    spans, start = [], None
    for i in range(n):
        if start is None and h[i] < h_on and v[i] < v_on:
            start = i
        elif start is not None and not (h[i] < h_off and v[i] < v_off):
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, n - 1))
    gap, merged = max(0, round(max_gap * fps)), []
    for a, b in spans:
        if merged and a - merged[-1][1] - 1 <= gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    shortest = max(2, round(min_time * fps))
    return [(a, b) for a, b in merged if b - a + 1 >= shortest]


def contact_weights(n, spans, blend):
    """Вес опоры по кадрам: 1 на отрезке, косинусный спад за blend кадров до и после, иначе 0 → (weights, span
    index per frame or None). Overlapping blends take the larger weight."""
    weight, owner = [0.0] * n, [None] * n
    for k, (a, b) in enumerate(spans):
        for i in range(max(0, a - blend), min(n, b + blend + 1)):
            d = a - i if i < a else (i - b if i > b else 0)
            w = 0.5 * (1 + math.cos(math.pi * d / (blend + 1))) if d else 1.0
            if w > weight[i]:
                weight[i], owner[i] = w, k
    return weight, owner


def lock_contacts(points, spans, blend):
    """Каждая опора — в одной точке (среднее по отрезку); за blend кадров до и после — косинусный переход."""
    means = [tuple(sum(p[k] for p in points[a:b + 1]) / (b - a + 1) for k in range(3)) for a, b in spans]
    weight, owner = contact_weights(len(points), spans, blend)
    return [p if owner[i] is None else lerp(p, means[owner[i]], weight[i]) for i, p in enumerate(points)]


def foot_slide(points, spans):
    """Скольжение: средний горизонтальный путь стопы за одну опору (в единицах точек)."""
    paths = [sum(math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]) for i in range(a, b))
             for a, b in spans]
    return sum(paths) / len(paths) if paths else 0.0
