"""Conservative suggestions for nearly stationary wrists in a solved motion.

These are review candidates, not proof of contact: a monocular video has no reliable
object surface or depth for deciding whether a hand is touching a prop.
"""
from __future__ import annotations

import math

from core.motion_cleanup import world_positions


def suggest(root, frames: list[dict], fps: float, *, enter_cm_s: float = 10.0,
            leave_cm_s: float = 18.0, min_seconds: float = 0.20,
            max_candidates: int = 100) -> list[dict]:
    """Find stable world-space wrist intervals to review and optionally pin with IK.

    Speed uses a centered difference and a 3-frame median. Hysteresis avoids splitting
    one hold due to a single noisy frame. Returned frame indices are zero-based.
    """
    try:
        fps = float(fps)
    except (TypeError, ValueError):
        raise ValueError("fps must be a positive finite number") from None
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be a positive finite number")
    if not (0 < enter_cm_s <= leave_cm_s <= 1000 and 0 < min_seconds <= 10):
        raise ValueError("invalid hand-hold thresholds")
    if not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if not frames:
        return []

    positions = world_positions(root, frames)
    minimum = max(2, math.ceil(min_seconds * fps))
    out = []
    for side in ("Left", "Right"):
        name = side + "Hand"
        if any(name not in row for row in positions):
            continue
        path = [row[name] for row in positions]
        raw = [0.0] * len(path)
        for i in range(1, len(path)):
            raw[i] = math.dist(path[i - 1], path[i]) * fps
        speed = []
        for i in range(len(path)):
            window = sorted(raw[max(0, i - 1):min(len(raw), i + 2)])
            speed.append(window[len(window) // 2])

        spans = []
        start = None
        for i, v in enumerate(speed):
            if start is None and v <= enter_cm_s:
                start = i
            elif start is not None and v > leave_cm_s:
                if i - start >= minimum:
                    spans.append((start, i - 1))
                start = None
        if start is not None and len(path) - start >= minimum:
            spans.append((start, len(path) - 1))

        for first, last in spans:
            drift = max((math.dist(path[first], p) for p in path[first:last + 1]), default=0.0)
            mean_speed = sum(speed[first:last + 1]) / (last - first + 1)
            out.append({"effector": name, "side": side, "first": first, "last": last,
                        "duration_s": round((last - first + 1) / fps, 3),
                        "mean_speed_cm_s": round(mean_speed, 2), "drift_cm": round(drift, 2)})
    out.sort(key=lambda c: (c["first"], c["side"]))
    return out[:max_candidates]
