"""MoCapGate — скелет тела SMPL / SMPL-X (22 сустава корпуса) для BVH.

GVHMR, WHAM, TRAM и GEM выдают движение в параметрах SMPL(-X): локальные
повороты суставов (axis-angle) относительно T-позы, у которой оси всех суставов
совпадают с мировыми. Поэтому BVH-скелет строится прямо из rest-позиций суставов
SMPL, и поворот SMPL переходит в BVH-канал без ретаргета.

Имена суставов — в стиле Mixamo: их понимают авто-ретаргет Blender (Rokoko,
Auto-Rig Pro) и HumanIK в Maya.

Rest-позиции:
- точные — из модели SMPLX_NEUTRAL.npz с учётом betas человека (нужен numpy и
  файл модели с https://smpl-x.is.tue.mpg.de, лицензия некоммерческая);
- без модели — встроенные приблизительные значения нейтральной SMPL-X
  (повороты всё равно корректны, слегка отличаются только длины костей).
"""
from __future__ import annotations
from core.skeleton import Joint

# Порядок суставов SMPL-X body (первые 22 совпадают с SMPL).
NAMES = (
    "Hips", "LeftUpLeg", "RightUpLeg", "Spine", "LeftLeg", "RightLeg", "Spine1",
    "LeftFoot", "RightFoot", "Spine2", "LeftToeBase", "RightToeBase", "Neck",
    "LeftShoulder", "RightShoulder", "Head", "LeftArm", "RightArm", "LeftForeArm",
    "RightForeArm", "LeftHand", "RightHand",
)
PARENTS = (-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19)
N_JOINTS = len(NAMES)

# Приблизительные rest-позиции нейтральной SMPL-X, метры, Y вверх, лицом к +Z.
DEFAULT_REST = (
    (0.003, -0.351, 0.012),    # Hips (pelvis)
    (0.061, -0.444, -0.014),   # LeftUpLeg
    (-0.060, -0.455, -0.009),  # RightUpLeg
    (0.000, -0.240, -0.015),   # Spine
    (0.116, -0.823, -0.006),   # LeftLeg (knee)
    (-0.104, -0.818, -0.003),  # RightLeg
    (0.010, -0.104, 0.006),    # Spine1
    (0.073, -1.237, -0.044),   # LeftFoot (ankle)
    (-0.089, -1.229, -0.043),  # RightFoot
    (-0.001, -0.055, 0.026),   # Spine2
    (0.120, -1.290, 0.083),    # LeftToeBase
    (-0.125, -1.285, 0.088),   # RightToeBase
    (-0.014, 0.110, -0.018),   # Neck
    (0.045, 0.029, 0.000),     # LeftShoulder (collar)
    (-0.049, 0.028, -0.006),   # RightShoulder
    (0.011, 0.268, -0.005),    # Head
    (0.171, 0.062, -0.021),    # LeftArm (shoulder)
    (-0.179, 0.064, -0.023),   # RightArm
    (0.420, 0.038, -0.046),    # LeftForeArm (elbow)
    (-0.423, 0.036, -0.047),   # RightForeArm
    (0.675, 0.038, -0.048),    # LeftHand (wrist)
    (-0.678, 0.040, -0.047),   # RightHand
)

# End Site для листьев, метры (в системе rest-позы).
_END_SITES = {
    "Head": (0.0, 0.16, 0.0),
    "LeftToeBase": (0.0, 0.0, 0.06),
    "RightToeBase": (0.0, 0.0, 0.06),
    "LeftHand": (0.09, 0.0, 0.0),
    "RightHand": (-0.09, 0.0, 0.0),
}


def rest_from_model(model_path: str, betas=None) -> list[tuple[float, float, float]]:
    """Точные rest-позиции 22 суставов из SMPLX_NEUTRAL.npz (или SMPL .npz) с учётом betas."""
    import numpy as np  # type: ignore

    m = np.load(model_path, allow_pickle=True)
    v = np.asarray(m["v_template"], dtype=np.float64)
    if betas is not None:
        b = np.asarray(betas, dtype=np.float64).reshape(-1)
        dirs = np.asarray(m["shapedirs"], dtype=np.float64)[:, :, : len(b)]
        v = v + dirs @ b
    jreg = m["J_regressor"]
    if hasattr(jreg, "toarray"):  # scipy.sparse в некоторых сборках модели
        jreg = jreg.toarray()
    joints = np.asarray(jreg, dtype=np.float64) @ v
    return [tuple(map(float, j)) for j in joints[:N_JOINTS]]


def build_skeleton(rest, scale: float = 100.0) -> Joint:
    """Дерево Joint из rest-позиций (метры) → оффсеты в BVH-единицах (по умолчанию см)."""
    joints = [Joint(n, (0.0, 0.0, 0.0)) for n in NAMES]
    for i, p in enumerate(PARENTS):
        if p < 0:
            continue
        joints[i].offset = tuple((rest[i][k] - rest[p][k]) * scale for k in range(3))  # type: ignore[assignment]
        joints[p].children.append(joints[i])
    for name, end in _END_SITES.items():
        joints[NAMES.index(name)].end_offset = tuple(e * scale for e in end)  # type: ignore[assignment]
    return joints[0]


def fk(global_orient, body_pose, transl, rest=DEFAULT_REST):
    """Мировые позиции 22 суставов (метры) одного кадра по формулам SMPL: таз = rest[0] + transl."""
    from core.rotations import axis_angle_to_matrix, mat_vec, matmul

    rv = [global_orient] + [body_pose[3 * i:3 * i + 3] for i in range(N_JOINTS - 1)]
    G: list = [None] * N_JOINTS
    P: list = [None] * N_JOINTS
    for i, p in enumerate(PARENTS):
        R = axis_angle_to_matrix(rv[i])
        if p < 0:
            G[i] = R
            P[i] = tuple(rest[0][k] + float(transl[k]) for k in range(3))
        else:
            G[i] = matmul(G[p], R)
            off = mat_vec(G[p], [rest[i][k] - rest[p][k] for k in range(3)])
            P[i] = tuple(P[p][k] + off[k] for k in range(3))
    return P
