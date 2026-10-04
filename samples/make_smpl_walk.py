#!/usr/bin/env python3
"""Процедурная «ходьба» в раскладке результатов GVHMR → samples/smpl_walk.json.

Нужна, чтобы проверить путь SMPL → BVH → Blender/Maya без GPU и без GVHMR:
    python3 samples/make_smpl_walk.py
    python3 mocapgate.py samples/smpl_walk.json -o samples/smpl_walk.bvh
"""
import json, math
from pathlib import Path

FPS, SECONDS = 30, 2.0


def frame(t: float):
    w = 2 * math.pi * t  # один двойной шаг в секунду
    pose = [[0.0, 0.0, 0.0] for _ in range(21)]  # body_pose: суставы 1..21

    def setj(j, v):
        pose[j - 1] = v

    setj(1, [-0.45 * math.sin(w), 0, 0])                     # LeftUpLeg
    setj(2, [0.45 * math.sin(w), 0, 0])                      # RightUpLeg
    setj(4, [0.7 * max(0.0, math.sin(w + 1.2)), 0, 0])        # LeftLeg (колено)
    setj(5, [0.7 * max(0.0, -math.sin(w + 1.2)), 0, 0])       # RightLeg
    setj(3, [0.05, 0.08 * math.sin(w), 0])                    # Spine: наклон + поворот
    setj(16, [0.35 * math.sin(w), 0, -1.25])                  # LeftArm: опущена, мах
    setj(17, [-0.35 * math.sin(w), 0, 1.25])                  # RightArm
    setj(18, [0, -0.3 - 0.2 * max(0.0, math.sin(w)), 0])      # LeftForeArm
    setj(19, [0, 0.3 + 0.2 * max(0.0, -math.sin(w)), 0])      # RightForeArm
    return {
        "global_orient": [0.0, 0.1 * math.sin(w), 0.0],
        "body_pose": [c for j in pose for c in j],
        "transl": [0.0, 0.03 * math.cos(2 * w), 1.2 * t],
    }


def main():
    fr = [frame(i / FPS) for i in range(int(FPS * SECONDS))]
    out = {"smpl_params_global": {k: [f[k] for f in fr] for k in ("global_orient", "body_pose", "transl")}}
    out["smpl_params_global"]["betas"] = [[0.0] * 10 for _ in fr]
    dst = Path(__file__).with_name("smpl_walk.json")
    dst.write_text(json.dumps(out), encoding="utf-8")
    print(f"{len(fr)} кадров -> {dst}")


if __name__ == "__main__":
    main()
