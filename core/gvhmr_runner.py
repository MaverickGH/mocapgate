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


def watch_parent(path, timeout=20):
    import signal
    import threading
    import time
    try:
        os.setsid()
    except OSError:
        pass
    def watch():
        previous = None
        last_change = time.monotonic()
        while True:
            try:
                current = Path(path).stat().st_mtime_ns
            except OSError:
                current = None
            if current != previous:
                last_change = time.monotonic()
                previous = current
            if time.monotonic() - last_change > timeout:
                if os.getpgrp() == os.getpid():
                    os.killpg(os.getpgrp(), signal.SIGTERM)
                else:
                    os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
    threading.Thread(target=watch, daemon=True).start()


def quote_path_overrides(overrides):
    return [key + '=' + json.dumps(value, ensure_ascii=False) if key in ('output_root','video_name') else item
            for item in overrides for key, _, value in [item.partition('=')]]


def track_configs(D, cfg, max_people, torch, fps=30, min_seconds=0.25):
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
        if len(frame_ids[pid]) < min(max(3, round(fps*min_seconds)), length):
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


def extract_in_batches(extract, images, boxes, torch, size=4):
    """Keep cropped video frames on CPU and send only a small batch to CUDA."""
    return torch.cat([extract(images[start:start+size], boxes[start:start+size])
                      for start in range(0, len(images), size)], dim=0)


def limit_preprocess_memory(D, torch):
    from hmr4d.utils.preproc.vitfeat_extractor import get_batch
    class Features(D.Extractor):
        def extract_video_features(self, video_path, bbx_xys, img_ds=0.5):
            images, boxes = get_batch(video_path, bbx_xys, img_ds=img_ds)
            extract = super().extract_video_features
            return extract_in_batches(extract, images, boxes, torch)
    class Pose(D.VitPoseExtractor):
        def extract(self, video_path, bbx_xys, img_ds=0.5):
            images, boxes = get_batch(video_path, bbx_xys, img_ds=img_ds)
            extract = super().extract
            return extract_in_batches(extract, images, boxes, torch)
    D.Extractor, D.VitPoseExtractor = Features, Pose


def tolerate_vo_failures(min_points=8):
    """Оценка движения камеры (SimpleVO, pycolmap) иногда не находит геометрию пары кадров: однотонный фон,
    смаз, мало совпадающих точек, камера почти стоит. Upstream тогда падает с
    «'NoneType' object has no attribute 'matrix'». Для такой пары берём «без движения» (единичную матрицу) —
    камера держит прежнее положение. Возвращает счётчик {"pairs", "failed"} для журнала."""
    import numpy as np
    try:
        from hmr4d.utils.preproc.relpose import solver_two_view as sv
    except ImportError:
        return {"pairs": 0, "failed": 0}
    counter = {"pairs": 0, "failed": 0}
    original = sv.PycolmapRansacTwoViewGeometrySolver.solve

    def solve(self, pts0, pts1):
        counter["pairs"] += 1
        try:
            if pts0 is None or len(pts0) < min_points:
                raise ValueError("too few matches")
            return original(self, pts0, pts1)
        except (AttributeError, ValueError, RuntimeError):
            counter["failed"] += 1
            return np.eye(4)
    sv.PycolmapRansacTwoViewGeometrySolver.solve = solve
    return counter


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gvhmr_dir")
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--f-mm", type=int, default=0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--max-people", type=int, choices=range(1, 9), default=4)
    ap.add_argument("--min-seconds", type=float, default=0.25)
    ap.add_argument("--heartbeat")
    a = ap.parse_args()
    if a.heartbeat:
        watch_parent(a.heartbeat)

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
    vo_failures = tolerate_vo_failures()  # пара кадров без решения — камера на ней неподвижна, а не сбой всей обработки

    if torch.cuda.get_device_properties(0).total_memory <= 10 * 1024**3:
        limit_preprocess_memory(D, torch)
        print("GPU: processing cropped frames in batches of 4", flush=True)
    compose = D.compose
    def safe_compose(*args, **kwargs):
        kwargs['overrides'] = quote_path_overrides(kwargs.get('overrides', []))
        return compose(*args, **kwargs)
    D.compose = safe_compose
    try:
        cfg = D.parse_args_to_cfg()
    finally:
        D.compose = compose
    print("STAGE preprocess", flush=True)
    tracks = track_configs(D, cfg, a.max_people, torch, a.fps, a.min_seconds) if a.max_people > 1 else [(1, cfg, 0, None)]
    for pid, person_cfg, _, _ in tracks:
        print(f"STAGE preprocess person {pid}", flush=True)
        D.run_preprocess(person_cfg)
        torch.cuda.empty_cache()
    if vo_failures["failed"]:
        share = vo_failures["failed"] / max(1, vo_failures["pairs"])
        print(f"INFO [MoCapGate] camera: {vo_failures['failed']} of {vo_failures['pairs']} frame pairs without camera "
              f"geometry — camera held still there" + ("; if the camera did not move, enable “Static camera”" if share > 0.3 else ""),
              flush=True)
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
