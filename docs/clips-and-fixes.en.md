# Game clips, fixing frames and take versions

[Русский](clips-and-fixes.ru.md) · [README](../README.en.md) · [Engine export](engines.en.md)

## Selecting a range

Below the video set **In frame** and **Out frame** (inclusive), or click **Set In** / **Set Out** on the current frame.
Keys: Space plays, ←/→ step a frame, I/O set the range. **Loop range** plays the range repeatedly, **Full take** resets
it. This works for a selected participant, not for All participants.

## Exporting a clip

**Export selected range** creates a separate ZIP in the take folder; source video and animation stay unchanged, each
export gets a unique name, and earlier variants remain available under **Download clip archive**.

| Option | Effect |
|---|---|
| **Clip: in place (keep jumps)** | Removes horizontal root travel; height, jumps and rotations remain |
| **Include FBX (Blender)** | Adds `capture.fbx` (capture skeleton, with expression blend shapes when present); needs Blender |
| **Seamless loop** | The last ~0.3 s blend into the first; yaw drift over the cycle is removed evenly. The clip becomes shorter by the blend length and starts after it |
| **Root bone (root motion)** | Adds a `Root` bone at the origin above `Hips` carrying floor travel and yaw |

### Editing the clip

**Edit the clip: mirror, speed, ease, turn** is applied to the range before Seamless loop and Root bone:

| Option | Effect |
|---|---|
| **Mirror (left ↔ right)** | Swaps the left and right sides; Left/Right facial curves are swapped too |
| **Put feet on the floor** | Shifts the motion so the feet stand on the floor |
| **Speed ×** | 0.1–10; motion is resampled in time, facial curves follow |
| **Turn around vertical, °** | Rotates the whole clip |
| **Path scale (bones unchanged)** | Scales root travel; bone lengths stay the same |
| **Ease in, s / Ease out, s** | Smooth start and end of the clip |

The edit parameters are recorded in `clip.json` (the `edit` field).

Archive contents:

- `capture.bvh` and `capture.ma` — the capture skeleton on the range frames;
- `character.ma` and `character.maya-tools.py` — Man_Rig when it is selected and prepared for the take
  (not created with **Root bone**: Man_Rig has no Root bone);
- `capture.face.csv` — facial curves for the same frames when present; a `FaceExpressions` node is added to the `.ma`;
- `capture.fbx` — optional;
- `clip.json` — range, frame count, FPS, duration, backend, root mode, loop and seam details.

## Markers

**+ Marker** or the **M** key names the current frame. Markers appear as yellow ticks on the timeline strip; jump to one from the markers list, and **×** deletes it. Markers are stored in `take.json`.

## Fixing frames

Select the bad range (In–Out) and click **Fix these frames**: the frames are replaced with a smooth interpolation of
their neighbours. The current result is saved as a version first. The participant's BVH and Maya scene are updated and
Man_Rig is rebuilt. Previously exported FBX, engine and character files for that participant become stale and are
removed from the list — export them again. This smooths over a glitch; it does not recover real motion.

The **Motion review** panel marks candidate problems (rotation and root-trajectory jumps, frames without
observations); the arrows jump between markers. A marker is a reason to look, not a proven error.

## Pose editing, foot contacts, curves and ghost poses

The **Pose editing and foot contacts** panel under the 3D view (one selected participant of a processed take):

- **Joint** — click a joint in 3D or pick it from the list; the selected one turns yellow. While editing, 3D shows the bones.
- **X / Y / Z sliders** rotate the joint at the current frame (in its local axes, on top of the captured motion); **Set key** keeps it. **Falloff, frames** — how many frames before the first and after the last key the edit fades out; between keys the rotation blends smoothly. Changes show immediately.
- **Curves**: the joint's Z / X / Y rotation over the whole take, yellow bars are keys; click to jump.
- **Foot contacts**: select In–Out and press “Left/Right foot planted on In–Out” or “Feet free on In–Out”. These correct the automatically detected contacts (rows L / R: green — added, red — removed).
- **Hold in place (IK)**: pick a hand or foot, select In–Out and press “Hold in place on In–Out (IK)” — it stays where it was
  at the In frame (hand on a table, foot on a step); the arm/leg is solved by IK with a 0.15 s transition. The body is not
  moved, so if it travels beyond the limb's reach the hand/foot reaches as far as it can (reported).
- **Apply edits** writes keys and contacts into the animation: BVH, Maya scene and Man_Rig are rebuilt; make FBX and engine/character files again; the previous version stays in “Previous animation versions”. Unsaved edits are kept in the take until applied or discarded.
- **Layout**: “Video and 3D side by side”, “Large 3D” or “Large video” (remembered).
- **Ghost poses** (next to the camera view): thin outlines 5 / 10 / 15 frames before (cyan) and after (orange) the current one — pops and paths are easy to spot.

Edits use the capture skeleton's local axes; on Mixamo rigs the X/Y/Z direction depends on the bone axes — check the result in 3D.

## Take versions

Before **Process again**, **Fix these frames** and **Apply edits** the finished result is archived under `versions/` in the take.
In **Previous animation versions** each version can be downloaded or **Restored**: animation, Maya scenes, Man_Rig and
the quality check go back to that version, while name, project, tags, notes and markers stay current.
The current animation is saved to versions first, so a restore can be undone too.
Source video and model environments are not included; versions are not deleted automatically and use disk space.
