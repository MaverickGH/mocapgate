# Video and animation frame rates

Studio probes frame timestamps and frame rates using ffprobe, storing video-timing.json with the take. Fractional rates remain fractional. The legacy MediaPipe path (CLI) processes frames sequentially at the input rate; variable-frame-rate video is normalized by timestamp using FFmpeg. GVHMR and GEM-X inputs are converted to 30 FPS; the pinned GVHMR upstream intermediate-video writer uses that rate.

New and existing takes offer export rates: Same as source video, 30, 60 or 120 FPS. VFR uses its average source rate for uniform BVH/FBX export. Translations interpolate by time and rotations use shortest-arc quaternion SLERP. Duration rounding is bounded by half an export frame when resampling, or a frame of video normalization. More exported frames do not imply additional recognized motion.

The take displays source, recognition and export rates. The legacy CLI --fps option now resamples animation instead of relabelling frame-rate metadata. Hydra configuration values for video names and output paths are quoted, supporting Unicode, spaces, brackets and equals signs.

## Verification, 2026-10-05

*Historical check: MediaPipe was the body model at the time.*


On macOS ARM64, real footage with people was transcoded to 24, 25, 30000/1001, 30, 50, 60000/1001, 60, 120, 240 FPS and VFR. This verifies encoded frame rates and timestamps; it does not turn the original recording into footage captured by a 240 FPS camera. MediaPipe, BVH and FBX exports passed at the source rate, 30, 60 and 120 FPS. Duration, mathematical root motion speed and shortest-arc rotation interpolation were checked. Reimporting 13 FBX files in Blender confirmed their animation timelines.

The unpacked native package additionally processed 25, 29.97, 120 FPS and VFR with all four export choices, including real conversion to 30 FPS. The Studio interface successfully processed and exported at the source 25 FPS. Reproduce with `python tests/verify_video_fps.py --output /absolute/test-output`; MediaPipe, FFmpeg and Blender must be installed.

GVHMR inference on NVIDIA was not run in this verification because this Mac has no NVIDIA GPU. Actual input conversion to 30 FPS and quoted paths parsed by Hydra were verified. Windows and Linux packages need separate validation. These changes exist since 0.3.3 beta (Windows prerelease); stable 0.3.2 lacks them.

## Recognition and export frame rate (0.3.3 beta)

- **Animation is exported at the source frame rate** (“Export FPS: same as source video”), e.g. 60 FPS.
- **Recognition**: GVHMR always runs at 30 FPS — the model is trained only at 30; the result is resampled to the export
  rate. GEM-X: “Recognition frame rate” — 30 (recommended) or “as the video” (up to 60, experimental: twice the memory
  and time, the model is trained at 30).
- **Recognition resolution** (long side, default 1920 px; 1280 for weak PCs) downsizes only the video given to the model:
  4K held in memory takes ~13 GB for 550 frames. Overlay and export are unchanged.
