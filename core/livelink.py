"""MoCapGate — facial curves → Live Link Face CSV (stdlib only).

Converts `<stem>.face.csv` (header `frame,time,<ARKit names>`, see core/face_export.py) into the CSV that the
Live Link Face iOS app records, so it can be brought into Unreal (Live Link Face importer / MetaHuman Animator
"Live Link Face" archives, or any tool that reads that CSV).

Format assumptions (from the Live Link Face app's recordings; not an Epic specification):
  * Header: `Timecode,BlendShapeCount,` followed by 61 curve columns: the 52 ARKit blendshapes with a capital
    first letter in the ARKit/Live Link order (EyeBlinkLeft … TongueOut), then HeadYaw, HeadPitch, HeadRoll,
    LeftEyeYaw, LeftEyePitch, LeftEyeRoll, RightEyeYaw, RightEyePitch, RightEyeRoll.
  * Timecode `HH:MM:SS:FF.mmm`: FF is the frame inside the second at the nominal (rounded) rate and `.mmm` the
    sub-frame fraction, written as `.000` because we sample whole frames. Non-drop-frame; starts at 00:00:00:00
    unless `start_seconds` is given. Fractional rates (29.97) use a nominal rate of round(fps).
  * BlendShapeCount is 61 on every row.
  * Curves missing from our CSV (and the head/eye rotation columns, which we do not capture) are 0.
  * Values are written with up to 6 significant digits.
"""
from __future__ import annotations
import csv
from pathlib import Path

ARKIT = (
    "EyeBlinkLeft", "EyeLookDownLeft", "EyeLookInLeft", "EyeLookOutLeft", "EyeLookUpLeft", "EyeSquintLeft",
    "EyeWideLeft", "EyeBlinkRight", "EyeLookDownRight", "EyeLookInRight", "EyeLookOutRight", "EyeLookUpRight",
    "EyeSquintRight", "EyeWideRight", "JawForward", "JawRight", "JawLeft", "JawOpen", "MouthClose", "MouthFunnel",
    "MouthPucker", "MouthRight", "MouthLeft", "MouthSmileLeft", "MouthSmileRight", "MouthFrownLeft",
    "MouthFrownRight", "MouthDimpleLeft", "MouthDimpleRight", "MouthStretchLeft", "MouthStretchRight",
    "MouthRollLower", "MouthRollUpper", "MouthShrugLower", "MouthShrugUpper", "MouthPressLeft", "MouthPressRight",
    "MouthLowerDownLeft", "MouthLowerDownRight", "MouthUpperUpLeft", "MouthUpperUpRight", "BrowDownLeft",
    "BrowDownRight", "BrowInnerUp", "BrowOuterUpLeft", "BrowOuterUpRight", "CheekPuff", "CheekSquintLeft",
    "CheekSquintRight", "NoseSneerLeft", "NoseSneerRight", "TongueOut",
)
ROTATIONS = ("HeadYaw", "HeadPitch", "HeadRoll", "LeftEyeYaw", "LeftEyePitch", "LeftEyeRoll",
             "RightEyeYaw", "RightEyePitch", "RightEyeRoll")
COLUMNS = ARKIT + ROTATIONS
HEADER = ("Timecode", "BlendShapeCount") + COLUMNS


def livelink_name(name: str) -> str:
    """ARKit name as written by MediaPipe (eyeBlinkLeft) → Live Link Face column (EyeBlinkLeft)."""
    return name[:1].upper() + name[1:]


def timecode(frame: int, fps: float, start_seconds: float = 0.0) -> str:
    """Frame index (0-based) → `HH:MM:SS:FF.mmm` at the nominal rate round(fps)."""
    nominal = max(1, round(fps))
    total = frame + round(start_seconds * nominal)
    ff, seconds = total % nominal, total // nominal
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}:{ff:02d}.000"


def rows(face_csv) -> tuple[list[str], list[list[float]]]:
    with open(face_csv, encoding="utf-8", newline="") as fh:
        table = [r for r in csv.reader(fh) if r]
    if not table or table[0][:2] != ["frame", "time"]:
        raise ValueError(f"not a MoCapGate face CSV: {face_csv}")
    return table[0][2:], [[float(v) for v in r[2:]] for r in table[1:]]


def write_livelink_csv(face_csv, out, fps: float, start_seconds: float = 0.0) -> int:
    """Write the Live Link Face CSV; returns the number of frames written."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    names, values = rows(face_csv)
    index = {livelink_name(n): i for i, n in enumerate(names)}
    lines = [",".join(HEADER)]
    for k, row in enumerate(values):
        curves = [row[index[c]] if c in index else 0.0 for c in COLUMNS]
        lines.append(",".join([timecode(k, fps, start_seconds), str(len(COLUMNS))] + [f"{v:.6g}" for v in curves]))
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(values)
