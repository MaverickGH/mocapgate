"""MoCapGate — математика поворотов на stdlib (без numpy).

Матрицы 3×3 — кортежи строк. Эйлер в порядке BVH-каналов ZXY:
R = Rz(z) · Rx(x) · Ry(y), углы в градусах.
"""
from __future__ import annotations
import math

Mat = tuple[tuple[float, float, float], ...]


def axis_angle_to_matrix(v) -> Mat:
    """Rodrigues: вектор оси, умноженный на угол (рад) → матрица поворота."""
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    a = math.sqrt(x * x + y * y + z * z)
    if a < 1e-12:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    x, y, z = x / a, y / a, z / a
    c, s = math.cos(a), math.sin(a)
    t = 1 - c
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def matmul(a: Mat, b: Mat) -> Mat:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)
    )  # type: ignore[return-value]


def mat_vec(m: Mat, v) -> tuple[float, float, float]:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))  # type: ignore[return-value]


def euler_zxy_to_matrix(z: float, x: float, y: float) -> Mat:
    z, x, y = math.radians(z), math.radians(x), math.radians(y)
    cz, sz, cx, sx, cy, sy = math.cos(z), math.sin(z), math.cos(x), math.sin(x), math.cos(y), math.sin(y)
    rz = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))
    rx = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    ry = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    return matmul(matmul(rz, rx), ry)


def matrix_to_euler_zxy(m: Mat) -> tuple[float, float, float]:
    """Матрица → (z, x, y) в градусах для R = Rz·Rx·Ry.

    Из разложения: m[2][1] = sin x, m[0][1] = -sin z·cos x, m[1][1] = cos z·cos x,
    m[2][0] = -cos x·sin y, m[2][2] = cos x·cos y.
    """
    sx = max(-1.0, min(1.0, m[2][1]))
    x = math.asin(sx)
    if abs(sx) < 0.999999:
        z = math.atan2(-m[0][1], m[1][1])
        y = math.atan2(-m[2][0], m[2][2])
    else:  # gimbal lock: z и y вырождаются в один угол, кладём всё в z
        y = 0.0
        z = math.atan2(m[1][0], m[0][0])
    return math.degrees(z), math.degrees(x), math.degrees(y)


def _wrap_near(a: float, ref: float) -> float:
    return a + 360.0 * round((ref - a) / 360.0)


def continuous_euler(zxy: tuple[float, float, float], prev: tuple[float, float, float] | None):
    """Выбрать эквивалентную тройку углов, ближайшую к предыдущему кадру.

    Без этого кривые в Blender/Maya дают скачки на ±360° и «кувырки» при
    интерполяции. Рассматриваем обе ветви решения ZXY (x и 180−x) и все
    сдвиги на 360°.
    """
    if prev is None:
        return zxy
    z, x, y = zxy
    best, best_d = zxy, float("inf")
    for cz, cx, cy in ((z, x, y), (z + 180.0, 180.0 - x, y + 180.0)):
        cand = (_wrap_near(cz, prev[0]), _wrap_near(cx, prev[1]), _wrap_near(cy, prev[2]))
        d = sum((c - p) ** 2 for c, p in zip(cand, prev))
        if d < best_d:
            best, best_d = cand, d
    return best


# ---------------------------------------------------------------- кватернионы (w, x, y, z)

def matrix_to_quat(m: Mat) -> tuple[float, float, float, float]:
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)  # type: ignore[return-value]


def quat_to_matrix(q) -> Mat:
    w, x, y, z = q
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
        (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
        (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)),
    )


def slerp(a, b, t: float):
    d = sum(p * q for p, q in zip(a, b))
    if d < 0:
        b, d = tuple(-c for c in b), -d
    if d > 0.9995:
        q = tuple(p + t * (r - p) for p, r in zip(a, b))
    else:
        th = math.acos(d)
        s = math.sin(th)
        wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s
        q = tuple(wa * p + wb * r for p, r in zip(a, b))
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def matrix_to_axis_angle(m: Mat) -> list[float]:
    w, x, y, z = matrix_to_quat(m)
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    s = math.sqrt(x * x + y * y + z * z)
    if s < 1e-12:
        return [0.0, 0.0, 0.0]
    a = 2 * math.atan2(s, w)
    return [x / s * a, y / s * a, z / s * a]


def transpose(m: Mat) -> Mat:
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def frame_from_axes(x, y) -> Mat:
    """Ортонормированный базис: X по x, Y — y без проекции на X, Z = X×Y. Столбцы = оси."""
    xn = _norm(x)
    d = sum(a * b for a, b in zip(y, xn))
    yn = _norm([y[i] - d * xn[i] for i in range(3)])
    zn = _cross(xn, yn)
    return tuple(tuple((xn, yn, zn)[c][r] for c in range(3)) for r in range(3))  # type: ignore[return-value]


def swing(a, b) -> Mat:
    """Кратчайший поворот, переводящий направление a в направление b."""
    a, b = _norm(a), _norm(b)
    c = _cross(a, b)
    s = math.sqrt(sum(v * v for v in c))
    d = sum(p * q for p, q in zip(a, b))
    if s < 1e-9:
        if d > 0:
            return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        perp = _cross(a, (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0))
        return axis_angle_to_matrix([v * math.pi for v in _norm(perp)])
    ang = math.atan2(s, d)
    return axis_angle_to_matrix([v / s * ang for v in c])


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1e-12
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
