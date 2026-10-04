"""Real-video acceptance check. Exit 1 means incorrect person count or identity.

python tools/check_multi_person_video.py
python tools/check_multi_person_video.py --landmarks path/to/landmarks.json
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/sports2d"
sys.path.insert(0, str(ROOT))


def evaluate_tracks(data, expected):
    failures, identities, samples = [], {}, []
    people = data.get("people", [])
    if len(people) != expected["expected_people"]:
        failures.append(f"Expected {expected['expected_people']} people, got {len(people)} IDs")
    if abs(data.get("fps", 0)-expected["fps"]) > .01:
        failures.append("Wrong FPS")
    if any(len(p["frames"]) != expected["frames"] for p in people) or not people:
        failures.append("Wrong timeline length")
    for sample in expected["samples"]:
        frame = sample["frame"]
        for label, (left, top, right, bottom) in sample["people"].items():
            matched = []
            for person in people:
                pose = person["frames"][frame] if frame < len(person["frames"]) else None
                if not pose:
                    continue
                points = pose["image"]
                x, y = [(points[23][axis]+points[24][axis])/2 for axis in (0, 1)]
                if left <= x <= right and top <= y <= bottom:
                    matched.append(person["id"])
            samples.append({"frame": frame, "person": label, "matched_ids": matched})
            if len(matched) != 1:
                failures.append(f"Frame {frame}, {label}: expected one pose, got {matched}")
            else:
                identities.setdefault(label, set()).add(matched[0])
    for label, ids in identities.items():
        if len(ids) != 1:
            failures.append(f"{label}: identity changed across frames: {sorted(ids)}")
    if len(identities) != expected["expected_people"]:
        failures.append("Not every annotated person was tracked")
    elif len(set().union(*identities.values())) < expected["expected_people"]:
        failures.append("One ID was used for different people")
    return {"passed": not failures, "failures": failures, "samples": samples,
            "person_ids": [p["id"] for p in people], "expected_people": expected["expected_people"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--landmarks", type=Path, help="validate an existing worker result without inference")
    ap.add_argument("--out", type=Path, default=ROOT / "dist/real-video-validation")
    args = ap.parse_args()
    expected = json.loads((FIXTURE / "expected.json").read_text())
    video = FIXTURE / expected["video"]
    if hashlib.sha256(video.read_bytes()).hexdigest() != expected["sha256"]:
        raise ValueError("Test video checksum does not match")
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.landmarks
    if path is None:
        from core.components import MediaPipe
        mp = MediaPipe()
        if not mp.installed() or not mp.model_path("heavy").is_file():
            print("Install MediaPipe heavy first: python mocapgate.py setup mediapipe")
            return 2
        path = args.out / "landmarks.json"
        mp.fetch_detector()
        proc = subprocess.run([str(mp.python()), str(ROOT / "core/pose_worker.py"), str(video),
                               "--model", str(mp.model_path("heavy")), "--detector-model", str(mp.detector_path()),
                               "--max-people", "4", "-o", str(path)],
                              env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        if proc.returncode:
            return proc.returncode
    result = evaluate_tracks(json.loads(path.read_text()), expected)
    result["source"] = expected["source"]
    (args.out / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
