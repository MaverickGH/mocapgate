# Two real people — Sports2D demo

`two_people.mp4`: a man jumps from a raised platform while a woman walks across
the frame. Different people, different movements, one original recording.
230 frames, 30 FPS, 1768×994. Intended person count: **2**.

Source: https://github.com/davidpagnon/Sports2D/blob/main/Sports2D/Demo/demo.mp4
Repository: https://github.com/davidpagnon/Sports2D
Copyright (c) 2022, perfanalytics. The repository's BSD 3-Clause license is retained
in `LICENSE`. This fixture is third-party material, separate from MoCapGate's MIT code.
Downloaded 2026-10-03, then transcoded from VP9 to H.264 with ffmpeg, CRF 18,
pixel format yuv420p, audio removed. Dimensions and frame rate preserved.
Original and included-file SHA-256 checksums are in `expected.json`.

`expected.json`: manually inspected pelvis regions at eight frames, with persistent
labels `jumper` and `walker`. These are coarse identity checks, not accurate 3D
motion ground truth or a benchmark for BVH rotation quality.

`detections.json.gz`: captured MediaPipe heavy detections from the first full run,
reconstructed from all retained tracks, before testing any fixes. It includes
duplicate poses. Detections from rejected tracks shorter than three observations
are absent. Replay tests isolate the association algorithm from model inference.

`baseline.json`: result of a fresh second run using MediaPipe 0.10.21 heavy,
max_people=4. Acceptance fails: nine IDs, and both people's sampled IDs change.
It records the historical bug; `expected.json` defines the desired outcome.
The regression test explicitly verifies that this old output fails acceptance.

`crop_detections.json.gz`: actual pose observations from the corrected pipeline:
EfficientDet Lite2 full-frame and tiled detection, box NMS, MediaPipe heavy in
each crop padded by 25%. Captured with maximum=4; 207 jumper and 163 walker
observations. `corrected.json` records a passing fresh count/identity check.
The ordinary suite replays these observations through the current tracker,
checks two persistent IDs and all manual samples, without an expected failure.

## Run a fresh check

Install MediaPipe heavy through Studio or `python mocapgate.py setup mediapipe`, then:

```powershell
python tools/check_multi_person_video.py
```

Results are written to `dist/real-video-validation`. Exit **0** means the count,
timeline and sampled identities passed; **1** means acceptance failed; **2** means
MediaPipe is not installed. Model inference errors retain the worker's exit code.
To check existing landmarks without running inference:

```powershell
python tools/check_multi_person_video.py --landmarks path/to/landmarks.json
```

The ordinary suite includes checksum verification and passing real identity
continuity. Fresh inference is a separate acceptance check. Count/identity
acceptance is not a benchmark of 3D rotation accuracy; motion quality is still
limited on this clip (32/100 and 30/100 in the individual reports).
The video is tracked in Git; build outputs remain in `dist`. Installers do not
include this test fixture.
