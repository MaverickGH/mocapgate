# Motion quality validation

The Studio's 0–100 take score is a **model-derived heuristic**, not an accuracy
measurement. Visibility, detector continuity, self-reported reprojection, joint
jitter and floor-foot motion can help flag suspicious takes, but none proves that
the reconstructed body matches the person. In particular, smoothing can lower
jitter while erasing a real landing or hand impact.

## Benchmark protocol

Keep the original source files unchanged and record SHA-256, duration, frame rate,
resolution, backend/model version, all processing options, output frame count and
the exact output take ID. Compare backends on the same frames and crop. Report
per-clip results and failures; do not average away a failed jump or identity swap.
Do not add licensed or user-supplied videos, body models, or derived frames to Git
without permission and rights to redistribute them.

For an independent accuracy claim, obtain synchronized reference motion for the
same action and coordinate frame, or manually annotate a held-out sample. Report:

* MPJPE in millimetres after a declared coordinate/unit alignment, and PA-MPJPE
  separately after rigid Procrustes alignment. The latter must not hide root/path
  error.
* Root trajectory error and MPJVE (velocity error) against reference timestamps.
* Foot-contact precision/recall against independently labelled contact intervals,
  plus planted-foot world speed and floor penetration during those intervals.
* Held-out-camera 2-D reprojection error only when its calibration is measured;
  never evaluate against the same detections used to fit the motion.
* For multiple people, ID switches and IDF1 using manually checked identity labels.

State the evaluated population, camera/view, occlusion, motion class, uncertainty,
and sample count. Compare each backend and each post-processing option on identical
inputs. Keep raw and corrected results side by side. Pre-register thresholds for a
release decision; there is no universal threshold that makes arbitrary monocular
video accurate.

## Multi-camera capture needed by this build

The `multiview-local` input currently requires separately recorded camera videos,
measured intrinsics and camera-to-world extrinsics, a shared world coordinate
system, explicit per-camera actor IDs, and a measured synchronization mapping.
A split-screen composite cannot provide these data. Use a rigid calibration board
(for example, a ChArUco board) visible across the full working volume to estimate
intrinsics/extrinsics; record the board dimensions. Record a shared synchronization
flash/clap visible or audible to every camera, retain source timestamps, and keep
cameras fixed after calibration. Inspect calibration residuals and held-out board
poses before importing a session. If the board is not visible across the volume,
or calibration/sync uncertainty is unknown, treat the take as uncalibrated and do
not describe its output as triangulated ground truth.

## Lessons from the reference projects

[`toyxyz_RGBMocap`](https://github.com/toyxyz/toyxyz_RGBMocap) documents multiple
body estimators, editable foot/palm contacts, and character retargeting;
[`prompt2rig`](https://github.com/blendi-remade/prompt2rig) separates the body
pass from a full-resolution hand pass, assigns detections back to body wrists,
tracks validity through time, and reports detection coverage. MoCapGate already
has a full-resolution MediaPipe hand pass, wrist-relative anatomical fitting,
contact editing, and retarget/export. This update exposes per-side hand detection
coverage in the take report as an informational diagnostic; it does not count
coverage as pose accuracy or subtract it from the overall heuristic score.

The reference demos are not proof of zero defects. RGB MoCap's validation notes
describe selected models, clips, and one Windows machine. Prompt2rig reports a
Windows RTX 4090 test and notes that hidden limbs, crossed arms, spins, and floor
work challenge monocular estimates. WiLoR is CC-BY-NC-ND; MANO, SMPL-X, GVHMR,
ExMR/FootMR, and some checkpoints carry separate non-commercial/provider terms.
This comparison does not add those models or code to MoCapGate's redistributable
package. Any separately approved optional backend would need its own license and
locally acquired model data.

### Local hand-smoothing trial (2026-10-29)

On the 93-frame, 60-FPS `Walk Angry` sample, the same saved GVHMR body result and
MediaPipe hand detections were exported with finger smoothing at 0, 0.45, and 0.70.
The Studio's rotation-jump review listed 30 candidates at 0, 19 at 0.45, and 18 at
0.70. Hand detection coverage remained 93/93 left and 73/93 right. These are
internal candidate counts, not ground-truth error counts; the small gain from 0.45
to 0.70 does not justify the stronger filtering on its own. New takes therefore
start at 0.45, while existing saved settings and the per-take slider remain in
control. This trial did not rerun body inference and did not compare finger angles
to a reference capture.

## Current evidence and next gate

Synthetic multiview tests verify geometry, parsing, synchronization checks, and
robust triangulation on known points. They do not measure model accuracy on a real
person. Existing local sample clips can compare failure modes and runtime between
backends, but without independent joint labels or calibrated cameras they cannot
support an MPJPE/IDF1 accuracy claim. The release gate for an accuracy claim is a
reproducible, permission-cleared reference set plus a separate evaluation report.
