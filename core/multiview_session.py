"""Validated session manifest and confidence-weighted 2-D→3-D actor fusion.

This module consumes independent per-camera 2-D detections. It deliberately
does not infer camera calibration or silently treat matching frame numbers as
matching timestamps. See ``docs/multiview-session.md`` for the manifest format.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
import math
from pathlib import Path
from typing import Any

from core.multiview import (CalibrationError, CameraCalibration, PointObservation,
                            TriangulationError, TriangulationPolicy, fit_clock_alignment,
                            timestamp_bracket, triangulate_point)

FORMAT = "mocapgate.multiview-session/1"
JOINT_COUNT = 33


@dataclass(frozen=True)
class SessionCamera:
    calibration: CameraCalibration
    video: Path
    crop: tuple[int, int, int, int] | None
    clock_scale: float
    clock_offset_s: float
    clock_uncertainty_s: float
    actor_tracks: dict[str, str]

    def session_time(self, local_time_s: float) -> float:
        return self.clock_scale * local_time_s + self.clock_offset_s


@dataclass(frozen=True)
class MultiViewSession:
    root: Path
    cameras: tuple[SessionCamera, ...]
    reference_camera_id: str
    policy: TriangulationPolicy
    max_timestamp_spread_s: float
    world_frame: str
    world_convention: str


def _number(value: Any, label: str, *, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"{label} is outside its valid range")
    return result


def _inside(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"{label} must be a relative file path")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the session folder") from exc
    if not candidate.is_file():
        raise ValueError(f"{label} does not exist: {relative}")
    return candidate


def load_session(path: str | Path) -> MultiViewSession:
    """Load a static-camera session; reject missing or ambiguous geometry early."""
    manifest = Path(path).resolve()
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("format") != FORMAT:
        raise ValueError(f"session format must be {FORMAT}")
    world = raw.get("world_frame")
    if not isinstance(world, str) or not world.strip():
        raise ValueError("world_frame must be explicitly named")
    convention = raw.get("world_convention")
    if convention != "y-up-right-handed":
        raise ValueError("world_convention must be explicitly set to y-up-right-handed for motion export")
    spread = _number(raw.get("max_timestamp_spread_s"), "max_timestamp_spread_s", minimum=0)
    if spread <= 0:
        raise ValueError("max_timestamp_spread_s must be positive")
    p = raw.get("triangulation_policy")
    if not isinstance(p, dict):
        raise ValueError("triangulation_policy is required; acceptance thresholds are never guessed")
    policy = TriangulationPolicy(
        huber_delta_px=_number(p.get("huber_delta_px"), "huber_delta_px", minimum=1e-9),
        minimum_ray_angle_deg=_number(p.get("minimum_ray_angle_deg"), "minimum_ray_angle_deg", minimum=1e-9),
        maximum_reprojection_error_px=_number(p.get("maximum_reprojection_error_px"), "maximum_reprojection_error_px", minimum=1e-9),
        minimum_condition_ratio=_number(p.get("minimum_condition_ratio"), "minimum_condition_ratio", minimum=1e-9),
        maximum_timestamp_spread_s=spread,
    )
    cameras_raw = raw.get("cameras")
    if not isinstance(cameras_raw, list) or len(cameras_raw) < 2:
        raise ValueError("at least two calibrated cameras are required")
    cameras = []
    ids = set()
    actors: set[str] | None = None
    for i, item in enumerate(cameras_raw):
        label = f"cameras[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        calibration = item.get("calibration")
        if not isinstance(calibration, dict):
            raise ValueError(f"{label}.calibration is required")
        camera_id = calibration.get("camera_id")
        if not isinstance(camera_id, str) or not camera_id.strip() or camera_id in ids:
            raise ValueError(f"{label} has a missing or duplicate camera_id")
        ids.add(camera_id)
        if calibration.get("stationary", True) is not True:
            raise CalibrationError(f"camera {camera_id}: moving cameras need a known per-frame trajectory")
        if calibration.get("world_frame", world) != world:
            raise CalibrationError(f"camera {camera_id}: world_frame does not match the session")
        cam = CameraCalibration(
            camera_id=camera_id,
            width=int(calibration.get("width", 0)), height=int(calibration.get("height", 0)),
            intrinsics=calibration.get("intrinsics"),
            rotation_world_to_camera=calibration.get("rotation_world_to_camera"),
            translation_world_to_camera=calibration.get("translation_world_to_camera"),
            distortion=tuple(calibration.get("distortion") or ()),
            unit=str(calibration.get("unit") or ""), world_frame=world,
            stationary=True,
            reprojection_rms_px=(None if calibration.get("reprojection_rms_px") is None
                                 else _number(calibration["reprojection_rms_px"], f"{label}.reprojection_rms_px", minimum=0)),
        )
        alignment = item.get("clock")
        if not isinstance(alignment, dict):
            raise ValueError(f"{label}.clock is required")
        scale = _number(alignment.get("scale"), f"{label}.clock.scale", minimum=1e-12)
        offset = _number(alignment.get("offset_s"), f"{label}.clock.offset_s")
        source = alignment.get("source")
        if source not in ("manual", "paired-events", "embedded-pts"):
            raise ValueError(f"{label}.clock.source must state how synchronization was established")
        event_count = int(alignment.get("event_count", 0))
        if event_count < 0 or (source == "paired-events" and event_count < 2):
            raise ValueError(f"{label}.clock.event_count is insufficient for the declared sync source")
        uncertainty = _number(alignment.get("uncertainty_s"), f"{label}.clock.uncertainty_s", minimum=0)
        if source == "paired-events":
            residual = _number(alignment.get("residual_rms_s"), f"{label}.clock.residual_rms_s", minimum=0)
            uncertainty = max(uncertainty, residual)
        if uncertainty > spread:
            raise ValueError(f"{label} synchronization uncertainty exceeds max_timestamp_spread_s")
        mapping = item.get("actor_tracks")
        if not isinstance(mapping, dict) or not mapping or any(not str(k).strip() or not str(v).strip() for k, v in mapping.items()):
            raise ValueError(f"{label}.actor_tracks must map session actor IDs to local track IDs")
        current = set(mapping)
        if actors is None:
            actors = current
        elif current != actors:
            raise ValueError("every camera must map the same set of session actor IDs")
        crop_raw = item.get("crop")
        crop = None
        if crop_raw is not None:
            if not isinstance(crop_raw, dict):
                raise ValueError(f"{label}.crop must be an x/y/width/height object")
            crop = tuple(int(crop_raw.get(k, 0)) for k in ("x", "y", "width", "height"))
            x, y, width, height = crop
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise ValueError(f"{label}.crop must have non-negative origin and positive size")
            if (width, height) != (cam.width, cam.height):
                raise CalibrationError(f"{label}: calibration dimensions must match the cropped detector image")
        cameras.append(SessionCamera(cam, _inside(manifest.parent, item.get("video"), f"{label}.video"), crop,
                                     scale, offset, uncertainty, {str(k): str(v) for k, v in mapping.items()}))
    ref = raw.get("reference_camera_id")
    if ref not in ids:
        raise ValueError("reference_camera_id must name one of the calibrated cameras")
    for a, b in combinations(cameras, 2):
        if a.clock_uncertainty_s + b.clock_uncertainty_s > spread:
            raise ValueError(f"combined synchronization uncertainty for {a.calibration.camera_id}/{b.calibration.camera_id} "
                             "exceeds max_timestamp_spread_s")
    return MultiViewSession(manifest.parent, tuple(cameras), ref, policy, spread, world, convention)


def fit_session_clocks(reference_events_s: list[float], local_events_s: list[float]) -> dict[str, float]:
    """Fit an affine local→session clock from paired events; at least two are required."""
    fit = fit_clock_alignment(reference_events_s, local_events_s)
    return {"source": "paired-events", "scale": fit.scale, "offset_s": fit.offset_s,
            "residual_rms_s": fit.residual_rms_s, "uncertainty_s": fit.residual_rms_s,
            "event_count": fit.event_count}


def _track_frames(landmarks: dict, local_track_id: str) -> list:
    matches = [p for p in landmarks.get("people", []) if str(p.get("id")) == str(local_track_id)]
    if not matches and str(local_track_id) == "1" and not landmarks.get("people"):
        frames = landmarks.get("frames")
    elif len(matches) == 1:
        frames = matches[0].get("frames")
    else:
        raise ValueError(f"local track {local_track_id!r} must identify exactly one tracked person")
    if not isinstance(frames, list):
        raise ValueError("pose detections must contain a frame list")
    return frames


def _at_time(frames: list, fps: float, camera: SessionCamera, session_time_s: float,
             max_gap_s: float) -> tuple[list | None, float | None]:
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("each camera needs a positive measured FPS")
    target = (session_time_s - camera.clock_offset_s) / camera.clock_scale
    times = [i / fps for i in range(len(frames))]
    bracket = timestamp_bracket(times, target, max_gap_s)
    if bracket is None:
        return None, None
    left, right, alpha = bracket
    a, b = frames[left], frames[right]
    if a is None or b is None:
        return None, None
    if len(a.get("image", [])) != JOINT_COUNT or len(b.get("image", [])) != JOINT_COUNT:
        raise ValueError("each detected pose must contain 33 MediaPipe image landmarks")
    pts = []
    for pa, pb in zip(a["image"], b["image"]):
        confidence = min(float(pa[2]), float(pb[2]))
        pts.append([(1-alpha)*float(pa[0])+alpha*float(pb[0]),
                    (1-alpha)*float(pa[1])+alpha*float(pb[1]), confidence])
    return pts, target


def fuse_actor_landmarks(session: MultiViewSession, detections: dict[str, dict],
                         actor_id: str, fps: float, *, max_gap_s: float = 0.1,
                         minimum_confidence: float = 0.2,
                         measurement_sigma_px: float = 3.0) -> dict:
    """Triangulate one session actor on the reference clock, retaining missing data as None.

    ``detections`` maps camera IDs to pose-worker output. A joint is emitted only
    when at least two independent calibrated views pass the configured geometric
    and reprojection checks.
    """
    if actor_id not in session.cameras[0].actor_tracks:
        raise ValueError(f"unknown session actor: {actor_id}")
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("output FPS must be positive")
    if not 0 <= minimum_confidence <= 1 or measurement_sigma_px <= 0:
        raise ValueError("invalid observation thresholds")
    by_id = {camera.calibration.camera_id: camera for camera in session.cameras}
    if set(detections) != set(by_id):
        raise ValueError("detections must be supplied for every and only calibrated camera")
    ref = by_id[session.reference_camera_id]
    ref_lm = detections[session.reference_camera_id]
    ref_frames = _track_frames(ref_lm, ref.actor_tracks[actor_id])
    ref_fps = float(ref_lm.get("fps") or 0)
    start_time = ref.session_time(0.0)
    count = max(0, int(math.floor((ref.session_time((len(ref_frames)-1)/ref_fps)-start_time)*fps+1e-6))+1) if ref_fps > 0 else 0
    result_frames = []
    diagnostics = {"joint_camera_count": [], "reprojection_error_px": [], "provenance": "triangulation"}
    for frame_index in range(count):
        session_time = start_time + frame_index / fps
        per_camera = {}
        for camera_id, camera in by_id.items():
            lm = detections[camera_id]
            local_id = camera.actor_tracks[actor_id]
            frames = _track_frames(lm, local_id)
            pts, mapped_time = _at_time(frames, float(lm.get("fps") or 0), camera,
                                        session_time, max_gap_s)
            if (pts is not None and mapped_time is not None
                    and camera.clock_uncertainty_s <= session.max_timestamp_spread_s):
                per_camera[camera_id] = pts
        points, counts, errors = [], [], []
        for joint in range(JOINT_COUNT):
            observations = []
            for camera_id, pts in per_camera.items():
                x, y, confidence = pts[joint]
                if confidence < minimum_confidence:
                    continue
                cam = by_id[camera_id].calibration
                observations.append(PointObservation(cam, (x*cam.width, y*cam.height), confidence,
                    measurement_sigma_px, by_id[camera_id].actor_tracks[actor_id], actor_id,
                    session_time, str(joint)))
            try:
                tri = triangulate_point(observations, session.policy)
                points.append([*tri.point_world, min(o.confidence for o in observations)])
                counts.append(len(tri.used_camera_ids))
                errors.append(max(tri.reprojection_error_px.values(), default=0.0))
            except TriangulationError:
                points.append(None); counts.append(0); errors.append(None)
        projected = []
        for point in points:
            if point is None:
                projected.append(None)
            else:
                (u, v), _depth = ref.calibration.project(point[:3])
                projected.append([u/ref.calibration.width, v/ref.calibration.height, point[3]])
        result_frames.append({"timestamp_s": session_time, "world": points,
                              "image": projected,
                              "provenance": ["triangulation" if p else "missing" for p in points]})
        diagnostics["joint_camera_count"].append(counts)
        diagnostics["reprojection_error_px"].append(errors)
    return {"actor_id": actor_id, "fps": fps, "frames": result_frames,
            "width": ref.calibration.width, "height": ref.calibration.height,
            "reference_calibration": {
                "camera_id": ref.calibration.camera_id,
                "width": ref.calibration.width, "height": ref.calibration.height,
                "intrinsics": ref.calibration.intrinsics,
                "rotation_world_to_camera": ref.calibration.rotation_world_to_camera,
                "translation_world_to_camera": ref.calibration.translation_world_to_camera,
                "distortion": ref.calibration.distortion,
                "unit": ref.calibration.unit, "world_frame": ref.calibration.world_frame,
                "reprojection_rms_px": ref.calibration.reprojection_rms_px,
            },
            "world_frame": session.world_frame, "unit": ref.calibration.unit,
            "diagnostics": diagnostics}


def triangulated_to_pose(fused: dict, smoothing: float = 0.5, root: str = "image",
                         rest=None) -> dict:
    """Convert fused metric MediaPipe landmarks into the shared SMPL pose format.

    Incomplete frames stay unobserved; only short internal gaps are linearly
    interpolated and retained in ``provenance``. The camera trajectory comes
    from triangulated pelvis points, not a single-view depth guess.
    """
    from core import retarget, smpl
    from core.filters import one_euro_series
    rest = rest or smpl.DEFAULT_REST
    fps = float(fused.get("fps") or 0)
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("fused motion needs a positive FPS")
    source = fused.get("frames") or []
    if not source:
        raise ValueError("fused motion contains no frames")
    critical = (retarget.NOSE, retarget.L_EAR, retarget.R_EAR, retarget.L_SH, retarget.R_SH,
                retarget.L_WR, retarget.R_WR, retarget.L_INDEX, retarget.R_INDEX,
                retarget.L_PINKY, retarget.R_PINKY, retarget.L_HIP, retarget.R_HIP,
                retarget.L_KNEE, retarget.R_KNEE, retarget.L_ANK, retarget.R_ANK,
                retarget.L_TOE, retarget.R_TOE)
    raw = [frame.get("world") or [] for frame in source]
    good = [len(points) == JOINT_COUNT and all(points[j] is not None for j in critical) for points in raw]
    if not any(good):
        raise ValueError("no frames have enough triangulated joints for a body pose")
    # Interpolate only gaps bracketed by measured poses and no longer than 100 ms.
    data = [[None if p is None else list(p[:3]) for p in pts] if len(pts) == JOINT_COUNT else [None]*JOINT_COUNT for pts in raw]
    provenance = [list(frame.get("provenance") or ["missing"]*JOINT_COUNT) for frame in source]
    maximum_gap = max(1, int(round(fps * 0.1)))
    good_indices = [i for i, ok in enumerate(good) if ok]
    if good_indices[0] > maximum_gap or len(source)-1-good_indices[-1] > maximum_gap:
        raise ValueError("the take begins or ends with too many frames without triangulated body joints")
    for a, b in zip(good_indices, good_indices[1:]):
        if b-a-1 > maximum_gap:
            raise ValueError(f"{b-a-1} consecutive frames lack triangulated body joints; split or review this interval")
        for i in range(a+1, b):
            alpha = (i-a)/(b-a)
            for j in critical:
                pa, pb = data[a][j], data[b][j]
                data[i][j] = [pa[k]*(1-alpha)+pb[k]*alpha for k in range(3)]
                provenance[i][j] = "interpolation"
            good[i] = False
    if len(good_indices) < 2:
        raise ValueError("fewer than two usable synchronized triangulated frames remain")
    usable = list(range(len(source)))
    # Fill non-critical joints from their nearest observed neighbor only for pose_frame completeness;
    # critical joints above remain the gate for accepting a measured pose.
    for j in range(JOINT_COUNT):
        known = [i for i in usable if data[i][j] is not None]
        if not known:
            continue
        for i in usable:
            if data[i][j] is None:
                nearest = min(known, key=lambda k: abs(k-i))
                data[i][j] = list(data[nearest][j])
                provenance[i][j] = "prediction"
    packed = [[p[j][k] for j in range(JOINT_COUNT) for k in range(3)] for p in (data[i] for i in usable)]
    packed = one_euro_series(packed, fps, max(0.0, min(1.0, float(smoothing))))
    world_by_frame = {i: [packed[n][3*j:3*j+3] for j in range(JOINT_COUNT)] for n, i in enumerate(usable)}
    go, bp, trans = [], [], []
    output_provenance = []
    output_landmarks = []
    base_pelvis = None
    for index in usable:
        pts = world_by_frame[index]
        g, body = retarget.pose_frame(pts, rest)
        pelvis = retarget._mid(pts[retarget.L_HIP], pts[retarget.R_HIP])
        if base_pelvis is None:
            base_pelvis = pelvis
        offset = [0.0, 0.0, 0.0] if root == "inplace" else [pelvis[k]-base_pelvis[k] for k in range(3)]
        go.append(g); bp.append(body); trans.append([offset[k]-rest[0][k] for k in range(3)])
        output_provenance.append(provenance[index])
        if not good[index]:
            output_landmarks.append(None)
            continue
        reference = fused["reference_calibration"]
        camera = CameraCalibration(reference["camera_id"], reference["width"], reference["height"],
            reference["intrinsics"], reference["rotation_world_to_camera"],
            reference["translation_world_to_camera"], tuple(reference.get("distortion") or ()),
            reference["unit"], reference["world_frame"], True, reference.get("reprojection_rms_px"))
        im, wm = [], []
        for j, point in enumerate(pts):
            (u, v), _depth = camera.project(point)
            original = raw[index][j]
            confidence = (float(original[3]) if original is not None and len(original) > 3
                          else 0.25 if provenance[index][j] == "interpolation" else 0.1)
            im.append([u/camera.width, v/camera.height, confidence])
            wm.append([*point, confidence])
        output_landmarks.append({"image": im, "world": wm})
    params = {"global_orient": go, "body_pose": bp, "transl": trans,
              "found": good, "fps": fps, "upper_body": False,
              "multiview_provenance": output_provenance,
              "multiview_source_frame_indices": usable,
              "multiview_reference_calibration": fused["reference_calibration"]}
    return {"params": params, "landmarks": {"fps": fps, "width": fused["width"],
            "height": fused["height"], "frames": output_landmarks},
            "fps": fps, "multiview_diagnostics": fused.get("diagnostics") or {}}
