"""MoCapGate — извлечение позы MediaPipe Pose Landmarker (запускается в venv компонента).

    <venv>/python core/pose_worker.py видео.mp4 --model pose_landmarker_heavy.task -o landmarks.json

Использует соседние person_detector/person_tracking и окружение mediapipe + opencv.
Печатает строки JSON-событий {"stage","progress","message"}
для Studio. Результат:
    {"fps", "width", "height", "frames": [ null | {"world": [[x,y,z,vis]×33],
                                                   "image": [[x,y,vis]×33]} ]}
world — метры, начало в центре бёдер, X вправо на изображении, Y вниз, Z к камере отрицательный
(система MediaPipe); image — доли кадра.
"""
from __future__ import annotations
import argparse, json, sys
if __package__:
    from .person_tracking import PoseTracker
    from .person_detector import PersonDetector
else:
    from person_tracking import PoseTracker
    from person_detector import PersonDetector


def emit(**kw):
    print(json.dumps(kw, ensure_ascii=True), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--model", required=True, help="pose_landmarker_*.task")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--max-people", type=int, choices=range(1, 9), default=4)
    ap.add_argument("--detector-model", help="EfficientDet Lite2 model (required for multiple people)")
    args = ap.parse_args()
    if args.max_people > 1 and not args.detector_model:
        ap.error("--detector-model is required for multiple people")

    import cv2  # type: ignore
    import mediapipe as mp  # type: ignore
    from mediapipe.tasks import python as mpt  # type: ignore
    from mediapipe.tasks.python import vision  # type: ignore

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        emit(stage="error", message=f"не открылось видео: {args.video}")
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if fps <= 1 or fps > 1000:  # webm из MediaRecorder часто без fps в заголовке
        fps = 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    opts = vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=args.model),
        running_mode=vision.RunningMode.IMAGE if args.max_people > 1 else vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    frames: list = []
    tracker = PoseTracker(max_gap=max(1, round(fps)))
    last_ts = -1
    detector = PersonDetector(args.detector_model) if args.max_people > 1 else None
    with vision.PoseLandmarker.create_from_options(opts) as lm:
        i = 0
        while True:
            ok, img = cap.read()
            if not ok or (args.max_frames and i >= args.max_frames):
                break
            # время по номеру кадра: у webm позиции в контейнере бывают «рваные»
            ts = max(int(i * 1000 / fps), last_ts + 1)
            last_ts = ts
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            boxes = detector.detect(rgb, args.max_people) if detector else [[0, 0, width, height, 1]]
            poses = []
            for bx, by, bw, bh, score in boxes:
                x, y = max(0, int(bx-bw*.25)), max(0, int(by-bh*.25))
                right, bottom = min(width, int(bx+bw*1.25)), min(height, int(by+bh*1.25))
                cw, ch = right-x, bottom-y
                if cw <= 0 or ch <= 0:
                    continue
                import numpy as np
                crop = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb[y:bottom, x:right]))
                res = lm.detect(crop) if detector else lm.detect_for_video(crop, ts)
                if not res.pose_landmarks:
                    continue
                w, im = res.pose_world_landmarks[0], res.pose_landmarks[0]
                pose = {
                    "world": [[round(p.x, 5), round(p.y, 5), round(p.z, 5), round(p.visibility or 0, 3)] for p in w],
                    "image": [[round((x+p.x*cw)/width, 5), round((y+p.y*ch)/height, 5), round(p.visibility or 0, 3)] for p in im],
                }
                if detector:
                    pose["bbox"] = [bx/width, by/height, bw/width, bh/height]
                poses.append(pose)
            tracker.update(poses)
            frames.append(poses[0] if poses else None)
            i += 1
            if i % 15 == 0:
                emit(stage="pose", progress=(i / total) if total else None, message=f"кадр {i}" + (f"/{total}" if total else ""))
    cap.release()
    if detector:
        detector.close()
    with open(args.out, "w", encoding="utf-8") as f:
        people = tracker.results()
        json.dump({"fps": fps, "width": width, "height": height,
                   "frames": people[0]["frames"] if people else frames, "people": people}, f)
    found = sum(1 for f in frames if f)
    emit(stage="pose", progress=1.0, message=f"поза найдена в {found} из {len(frames)} кадров")
    return 0 if people else 2


if __name__ == "__main__":
    sys.exit(main())
