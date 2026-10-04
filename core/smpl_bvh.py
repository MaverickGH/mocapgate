"""MoCapGate — движение SMPL(-X) → кадры BVH.

Вход — параметры одной последовательности (как у GVHMR/WHAM/TRAM/GEM):
    global_orient  L×3   axis-angle корня (рад)
    body_pose      L×63  axis-angle 21 сустава корпуса (или L×69 у SMPL — берём первые 63)
    transl         L×3   смещение корня (метры)
    betas          10    форма тела (опц., нужна только для точных длин костей)

В SMPL позиция таза в мире = rest(таз) + transl, а поворот каждого сустава
задан в системе родителя при единичных осях rest-позы. Ровно так же устроен
BVH, поэтому каждый поворот переводится в Эйлер ZXY напрямую.

params["cam_to_yup"] = True — вход в камерной системе OpenCV (Y вниз, Z от
камеры, режим incam): весь мир поворачиваем на 180° вокруг X.
"""
from __future__ import annotations
from core import smpl
from core.rotations import axis_angle_to_matrix, continuous_euler, mat_vec, matmul, matrix_to_euler_zxy
from core.skeleton import Joint


def mean_betas(betas) -> list[float] | None:
    """betas бывают на кадр (L×10) — усредняем; форма тела в ролике одна."""
    if betas is None or len(betas) == 0:
        return None
    if isinstance(betas[0], (int, float)):
        return [float(b) for b in betas]
    n = len(betas)
    return [sum(float(row[k]) for row in betas) / n for k in range(len(betas[0]))]


def convert(params: dict, model_path: str | None = None, scale: float = 100.0) -> tuple[Joint, list[dict]]:
    """Вернуть (скелет, кадры) для core.bvh.write. scale=100 → сантиметры."""
    go, bp, tr = params["global_orient"], params["body_pose"], params["transl"]
    if not (len(go) == len(bp) == len(tr)):
        raise ValueError(f"разная длина последовательностей: {len(go)}/{len(bp)}/{len(tr)}")
    betas = mean_betas(params.get("betas"))

    rest = smpl.rest_from_model(model_path, betas) if model_path else list(smpl.DEFAULT_REST)
    root = smpl.build_skeleton(rest, scale)
    pelvis = rest[0]
    flip = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0)) if params.get("cam_to_yup") else None

    frames: list[dict] = []
    prev: dict[str, tuple[float, float, float]] = {}
    for f in range(len(go)):
        pose = list(bp[f])
        if len(pose) < 63:
            raise ValueError(f"кадр {f}: body_pose длиной {len(pose)}, нужно ≥63")
        rotvecs = [go[f]] + [pose[3 * i: 3 * i + 3] for i in range(smpl.N_JOINTS - 1)]
        frame: dict = {}
        for name, rv in zip(smpl.NAMES, rotvecs):
            m = axis_angle_to_matrix(rv)
            if flip and name == "Hips":
                m = matmul(flip, m)
            e = continuous_euler(matrix_to_euler_zxy(m), prev.get(name))
            prev[name] = e
            frame[name] = {"rot": e}
        pos = tuple(pelvis[k] + float(tr[f][k]) for k in range(3))
        if flip:
            pos = mat_vec(flip, pos)
        frame["Hips"]["pos"] = tuple(c * scale for c in pos)
        frames.append(frame)
    return root, frames
