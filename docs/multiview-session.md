# Calibrated multi-view session format

`mocapgate.multiview-session/1` is the input contract for the static-camera
multi-view path. It is intentionally explicit: a composite video is not camera
calibration, equal frame numbers are not synchronization, and unknown geometry
must not be filled with guessed values.

The manifest lives next to its camera videos. Every `video` path is relative to
that folder and must stay inside it. Every camera calibration must describe the
video after any crop/resize used for detection. Extrinsics map a point from the
named session world frame into OpenCV camera coordinates (`x` right, `y` down,
`z` forward); translations and reconstructed points use the same declared unit.
The Studio's motion retargeter expects a Y-up world frame, so calibrations used
for animation must name a Y-up frame and express their transforms accordingly.
The manifest must declare `world_convention: "y-up-right-handed"`; unsupported
or omitted axis conventions are rejected before processing.

Each camera entry must contain `video`, `clock`, `actor_tracks`, and
`calibration`. `calibration` requires `camera_id`, `width`, `height`, the 3×3
`intrinsics` matrix, 3×3 `rotation_world_to_camera`, 3-value
`translation_world_to_camera`, `distortion`, `unit`, `world_frame`, and
`stationary`. `reprojection_rms_px` is optional only when the calibration tool
cannot report it. `actor_tracks` explicitly maps each shared session actor to a
camera-local pose-worker track ID.

`clock` requires `source`, `scale`, `offset_s`, `uncertainty_s`, and
`event_count`. `source` is `manual`, `paired-events`, or `embedded-pts`. For
`paired-events`, include `residual_rms_s` and at least two paired events.
`uncertainty_s` must not exceed the session's declared maximum timestamp
spread. The triangulation policy values must be chosen from the actual
calibration quality, camera baseline, and image scale; there are no defaults.

A production session should record the calibration method, target dimensions,
per-camera clock source, source PTS, and calibration reprojection error. The
first implementation accepts independent
2-D pose detections and emits a 3-D point only when at least two views pass the
explicit triangulation checks. Missing joints remain missing; the fusion layer
does not invent detections or call a single-view estimate a triangulation.
