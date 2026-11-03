"""MoCapGate — общая сцена для участников GEM-X: где стоял человек относительно камеры, по гравитации.

GEM-X отдаёт два набора параметров тела:
- в системе камеры (incam): настоящее положение и высота человека относительно камеры (OpenCV: Y вниз);
- «мировые» (global): ориентация по гравитации, но траектория собрана из скоростей от нуля — высота
  относительно камеры и взаимное расположение людей теряются.

Берём положение из камеры, а вертикаль — из разницы ориентаций корня: R = G_t · C_tᵀ (камера → мир),
усреднённую по кадрам и по всем участникам (камера неподвижна). Пол — по стопам: Y = 0 на нижнем
перцентиле высоты стоп всех участников, камера остаётся на своей высоте над полом.
Только stdlib — проверяется тестами без torch.
"""
from __future__ import annotations
import math

from core import smpl
from core.rotations import matmul, matrix_to_quat, quat_to_matrix, transpose, mat_vec

# сустав SMPL (для проверки качества) ← имена SOMA после алиасов раннера, по порядку предпочтения
REPORT_NAMES = {
    "LeftToeBase": ("LeftToeBase", "LeftToe", "LeftToe_End", "LeftFoot"),
    "RightToeBase": ("RightToeBase", "RightToe", "RightToe_End", "RightFoot"),
    "Spine": ("Spine",), "Spine1": ("Spine1", "Spine"), "Spine2": ("Spine2", "Chest", "Spine1"),
    "Neck": ("Neck", "Neck1", "Neck2"),
}


def average_rotation(mats: list) -> tuple:
    """Средний поворот: кватернионы в одной полусфере, сумма, нормировка."""
    acc, ref = [0.0, 0.0, 0.0, 0.0], None
    for m in mats:
        q = matrix_to_quat(m)
        if ref is None:
            ref = q
        if sum(a * b for a, b in zip(q, ref)) < 0:
            q = tuple(-c for c in q)
        acc = [a + c for a, c in zip(acc, q)]
    n = math.sqrt(sum(c * c for c in acc)) or 1.0
    return quat_to_matrix(tuple(c / n for c in acc))


def camera_to_world(global_roots: list, camera_roots: list) -> tuple:
    """R = G_t · C_tᵀ по кадрам (и участникам) → один поворот камера → мир по гравитации."""
    return average_rotation([matmul(g, transpose(c)) for g, c in zip(global_roots, camera_roots)])


def anchor_offset(R, camera_roots: list, global_roots: list) -> list:
    """Сдвиг мировой траектории к месту человека относительно камеры.

    Положение по камере (incam) дрожит по глубине — его считают по размеру рамки; мировая траектория
    плавная, но собрана от нуля. Сдвигаем плавную траекторию целиком на медиану разницы:
    движение остаётся плавным, а человек стоит там, где был относительно камеры, на своей высоте.
    """
    diffs = [[a - b for a, b in zip(mat_vec(R, c), g)] for c, g in zip(camera_roots, global_roots)]
    out = []
    for k in range(3):
        values = sorted(d[k] for d in diffs)
        out.append(values[len(values) // 2] if values else 0.0)
    return out


def floor_height(people_joints: list, foot_indices: list, percentile: float = 0.1) -> float:
    """Высота пола: нижний перцентиль по кадрам минимальной высоты стоп (всех участников)."""
    lows = sorted(min(frame[j][1] for j in foot_indices) for joints in people_joints for frame in joints if frame)
    return lows[int(percentile * (len(lows) - 1))] if lows else 0.0


def project(points: list, K) -> list:
    """Точки в системе камеры OpenCV → пиксели кадра."""
    out = []
    for x, y, z in points:
        z = z if abs(z) > 1e-6 else 1e-6
        out.append([round(K[0][0] * x / z + K[0][2], 1), round(K[1][1] * y / z + K[1][2], 1)])
    return out


def report_indices(names: list) -> list:
    """Индексы суставов SOMA в порядке 22 суставов SMPL — для общей проверки качества."""
    index = {n: i for i, n in enumerate(names)}
    out = []
    for name in smpl.NAMES:
        found = next((index[c] for c in REPORT_NAMES.get(name, (name,)) if c in index), None)
        if found is None:
            raise ValueError(f"в скелете SOMA нет сустава для {name}")
        out.append(found)
    return out


def foot_indices(names: list) -> list:
    index = {n: i for i, n in enumerate(names)}
    feet = [index[n] for n in ("LeftFoot", "RightFoot", "LeftToe_End", "RightToe_End", "LeftToeBase", "RightToeBase",
                               "LeftToe", "RightToe") if n in index]
    if not feet:
        raise ValueError("в скелете SOMA нет стоп")
    return feet
