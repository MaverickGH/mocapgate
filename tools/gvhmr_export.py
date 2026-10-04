#!/usr/bin/env python3
"""Результаты GVHMR (.pt) → JSON, который MoCapGate читает без torch.

Запускать там, где работает GVHMR (Colab/облако, torch уже стоит):
    python gvhmr_export.py outputs/demo/<клип>/hmr4d_results.pt [-o клип.gvhmr.json]

Файл самодостаточный — без импортов MoCapGate, его можно просто скопировать в Colab.
"""
import argparse
import json
from pathlib import Path

import torch

KEYS = ("global_orient", "body_pose", "transl", "betas")


def main() -> None:
    ap = argparse.ArgumentParser(description="GVHMR hmr4d_results.pt → JSON для MoCapGate")
    ap.add_argument("results", help="hmr4d_results.pt")
    ap.add_argument("-o", "--out", help="выходной JSON (по умолчанию рядом, .json)")
    ap.add_argument("--fps", type=float, default=30.0, help="fps видео, поданного в GVHMR (по умолчанию 30)")
    args = ap.parse_args()

    pred = torch.load(args.results, map_location="cpu", weights_only=False)
    out = {"format": "mocapgate.take/1", "source": "gvhmr", "fps": args.fps}
    for space in ("smpl_params_global", "smpl_params_incam"):
        if space in pred:
            out[space] = {k: pred[space][k].float().tolist() for k in KEYS if k in pred[space]}
    if "K_fullimg" in pred:
        out["K_fullimg"] = pred["K_fullimg"][0].float().tolist()  # интринсики первого кадра
    dst = Path(args.out or Path(args.results).with_suffix(".json"))
    dst.write_text(json.dumps(out), encoding="utf-8")
    n = len(out.get("smpl_params_global", {}).get("transl", []))
    print(f"{n} кадров -> {dst}")


if __name__ == "__main__":
    main()
