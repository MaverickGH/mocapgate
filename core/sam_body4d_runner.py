"""Experimental SAM-Body4D worker; run with its own Python, never Studio's.

Exports MHR keypoints for visual comparison, not SMPL parameters or BVH.
Requires the pinned upstream checkout and user-obtained model checkpoints.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

UPSTREAM_COMMIT = '21af1020979ef32ddf6be3597ef59a68bad2f1bf'
EXPORT_KEYS = ('pred_keypoints_2d', 'pred_keypoints_3d', 'pred_cam_t',
               'global_rot', 'body_pose_params', 'mhr_model_params')


def capture_record(frame, person_id, output):
    values = {}
    for key in EXPORT_KEYS:
        value = output.get(key)
        if value is not None:
            if hasattr(value, 'detach'):
                value = value.detach().cpu()
            values[key] = value.tolist() if hasattr(value, 'tolist') else value
    if 'pred_keypoints_2d' not in values:
        raise ValueError('Upstream output is missing pred_keypoints_2d')
    return {'frame': frame, 'id': int(person_id), **values}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('repository', type=Path)
    ap.add_argument('video', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--completion', action='store_true', help='enable diffusion occlusion completion')
    ap.add_argument('--batch-size', type=int, default=4)
    ap.add_argument('--checkpoint-root', type=Path, help='directory containing user-obtained upstream models')
    args = ap.parse_args()
    repo, video, output = [p.resolve() for p in (args.repository, args.video, args.output)]
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != UPSTREAM_COMMIT:
        raise RuntimeError(f'Expected SAM-Body4D commit {UPSTREAM_COMMIT}, got {revision}')
    if args.batch_size < 1:
        ap.error('--batch-size must be positive')
    if output.exists():
        raise FileExistsError(f'Use a new output directory: {output}')
    from omegaconf import OmegaConf
    config = OmegaConf.load(repo / 'configs/body4d.yaml')
    if args.checkpoint_root:
        config.paths.ckpt_root = str(args.checkpoint_root.resolve())
    config.completion.enable = args.completion
    config.sam_3d_body.batch_size = args.batch_size
    required = [config.sam3.ckpt_path, config.sam_3d_body.ckpt_path,
                config.sam_3d_body.mhr_path, config.sam_3d_body.fov_path]
    if args.completion:
        required += [config.completion.model_path_mask, config.completion.model_path_rgb,
                     config.completion.model_path_depth]
    missing = [str(p) for p in required if not Path(p).exists()]
    if missing:
        raise FileNotFoundError('Missing user-obtained SAM-Body4D checkpoints; set --checkpoint-root:\n'
                                + '\n'.join(missing))
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('This experiment requires NVIDIA CUDA; MPS/CPU is unverified')
    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if not (fps > 0 and count > 0 and width > 0 and height > 0):
        raise ValueError('Cannot read video timing')
    output.mkdir(parents=True)
    os.chdir(repo)
    sys.path[:0] = [str(repo), str(repo / 'models/sam_3d_body'), str(repo / 'models/diffusion_vas')]
    spec = importlib.util.spec_from_file_location('body4d_offline', repo / 'scripts/offline_app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config.runtime.output_dir = str(output)
    # Use an experiment-local config; never overwrite upstream or Studio settings.
    config_file = output / 'config.yaml'
    OmegaConf.save(config, config_file)
    original_app = module.OfflineApp
    class ExperimentApp(original_app):
        def __init__(self):
            super().__init__(str(config_file))
    module.OfflineApp = ExperimentApp
    records = []
    original_save = module.save_mesh_results
    def save_with_keypoints(*, outputs, faces, save_dir, focal_dir, image_path, id_current):
        frame = int(Path(image_path).stem)
        if outputs is not None:
            if len(outputs) != len(id_current):
                raise ValueError('Upstream person IDs do not match predictions')
            records.extend(capture_record(frame, pid, prediction)
                           for pid, prediction in zip(id_current, outputs))
        original_save(outputs, faces, save_dir, focal_dir, image_path, id_current)
    module.save_mesh_results = save_with_keypoints
    # Frame directories avoid upstream's video probe starting at frame 10 and
    # running beyond short clips. Preserve every frame with explicit indices.
    images = output / 'input_frames'
    images.mkdir()
    cap = cv2.VideoCapture(str(video))
    decoded = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if not cv2.imwrite(str(images / f'{decoded:08d}.jpg'), frame):
                raise OSError('Cannot write input frame')
            decoded += 1
    finally:
        cap.release()
    if decoded != count or count > 1800:
        raise ValueError('Use a fully decodable clip of at most 1800 frames')
    completed = False
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    try:
        module.inference(argparse.Namespace(input_video=str(images), output_dir=str(output)))
        completed = True
    finally:
        with video.open('rb') as stream:
            video_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        data = {'format': 'mocapgate.sam-body4d-experiment/1', 'source': 'sam-body4d',
                'revision': revision, 'fps': fps, 'frames': count, 'width': width, 'height': height,
                'video_sha256': video_hash, 'completed': completed,
                'elapsed_seconds': time.monotonic() - started,
                'cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                'completion': args.completion, 'batch_size': args.batch_size,
                'coordinate_space': 'upstream MHR camera coordinates; not world-grounded SMPL',
                'records': records}
        with (output / 'keypoints.json').open('w') as stream:
            json.dump(data, stream, allow_nan=False)
    print('RESULT', output / 'keypoints.json', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
