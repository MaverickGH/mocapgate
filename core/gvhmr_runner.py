"""MoCapGate — запуск GVHMR без рендера (Colab и свой компьютер с NVIDIA GPU).

    <python окружения GVHMR> gvhmr_runner.py <папка GVHMR> <видео 30 fps> <папка вывода> [--static] [--f-mm N]

Выполняется ИНТЕРПРЕТАТОРОМ GVHMR (там torch/hydra/pytorch3d), поэтому без импортов MoCapGate.
Повторяет предсказание из tools/demo/demo.py, но пропускает рендер: тогда нужна только модель
SMPL-X (рендер требует ещё SMPL .pkl). Печатает «RESULT <путь к дублю JSON>».
"""
import argparse
import json
import os
import sys
from pathlib import Path
from copy import deepcopy


def track_configs(D, cfg, max_people, torch, fps=30):
    """Seed GVHMR's bbox cache per YOLO ID instead of selecting its top track."""
    from hmr4d.utils.seq_utils import (frame_id_to_mask, rearrange_by_mask,
                                      get_frame_id_list_from_mask, linear_interpolate_frame_ids)
    from hmr4d.utils.net_utils import moving_average_smooth
    tracker = D.Tracker()
    history = tracker.track(cfg.video_path)
    frame_ids, boxes, ordered = tracker.sort_track_length(history, cfg.video_path)
    del tracker
    result = []
    length = len(history)
    for pid in ordered:
        # Require a quarter-second of evidence before exporting a new person.
        # A few tracker observations at the frame edge are often a split ID.
        if len(frame_ids[pid]) < min(max(3, round(fps*.25)), length):
            continue
        person_cfg = deepcopy(cfg)
        # Resolve interpolation before changing folders; every person shares the same video/timebase.
        paths = {k: str(v) for k, v in cfg.paths.items()}
        folder = Path(cfg.output_dir) / f"person_{pid}"
        folder.mkdir(parents=True, exist_ok=True)
        person_cfg.output_dir = folder.as_posix()
        person_cfg.preprocess_dir = folder.as_posix()
        person_cfg.video_path = cfg.video_path
        for key, value in paths.items():
            person_cfg.paths[key] = (folder / Path(value).name).as_posix()
        ids = torch.tensor(frame_ids[pid])
        mask = frame_id_to_mask(ids, length)
        bbx = rearrange_by_mask(torch.tensor(boxes[pid]), mask)
        bbx = linear_interpolate_frame_ids(bbx, get_frame_id_list_from_mask(~mask))
        bbx = moving_average_smooth(moving_average_smooth(bbx, window_size=5, dim=0), window_size=5, dim=0)
        torch.save({"bbx_xyxy": bbx.float(),
                    "bbx_xys": D.get_bbx_xys_from_xyxy(bbx, base_enlarge=1.2).float()}, person_cfg.paths.bbx)
        result.append((int(pid), person_cfg, min(frame_ids[pid]), max(frame_ids[pid])))
        if len(result) >= max_people:
            break
    if not result:
        raise RuntimeError("GVHMR не нашёл участников")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gvhmr_dir")
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--f-mm", type=int, default=0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--max-people", type=int, choices=range(1, 9), default=4)
    a = ap.parse_args()

    gv = os.path.abspath(a.gvhmr_dir)
    video = Path(a.video).resolve().as_posix()
    out_dir = Path(a.out_dir).resolve()
    sys.path[:0] = [gv, os.path.join(gv, "tools", "demo")]
    os.chdir(gv)
    sys.argv = ["demo.py", "--video", video, "--output_root", out_dir.as_posix()] + \
        (["-s"] if a.static else []) + (["--f_mm", str(a.f_mm)] if a.f_mm else [])

    import hydra  # noqa: E402
    import torch  # noqa: E402
    import demo as D  # noqa: E402  tools/demo/demo.py

    cfg = D.parse_args_to_cfg()
    print("STAGE preprocess", flush=True)
    tracks = track_configs(D, cfg, a.max_people, torch, a.fps) if a.max_people > 1 else [(1, cfg, 0, None)]
    for pid, person_cfg, _, _ in tracks:
        print(f"STAGE preprocess person {pid}", flush=True)
        D.run_preprocess(person_cfg)
        torch.cuda.empty_cache()
    print("STAGE predict", flush=True)
    model = hydra.utils.instantiate(cfg.model, _recursive_=False)
    model.load_pretrained_model(cfg.ckpt_path)
    model = model.eval().cuda()
    keys = ("global_orient", "body_pose", "transl", "betas")
    take = {"format": "mocapgate.scene/1", "source": "gvhmr", "fps": a.fps, "people": [],
            "options": {"static_camera": a.static, "focal_mm": a.f_mm or None}}
    for pid, person_cfg, start, end in tracks:
        print(f"STAGE predict person {pid}", flush=True)
        data = D.load_data_dict(person_cfg)
        with torch.no_grad():
            pred = D.detach_to_cpu(model.predict(data, static_cam=cfg.static_cam))
        torch.save(pred, person_cfg.paths.hmr4d_results)
        person = {"id": pid, "start_frame": start,
                  "end_frame": end if end is not None else len(pred["smpl_params_global"]["transl"])-1}
        for space in ("smpl_params_global", "smpl_params_incam"):
            person[space] = {k: pred[space][k].float().tolist() for k in keys if k in pred[space]}
        person["K_fullimg"] = pred["K_fullimg"][0].float().tolist()
        take["people"].append(person)
        del data, pred
        torch.cuda.empty_cache()
    out = str(out_dir / "result.mocapgate.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(take, f)
    print("RESULT", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
