# Character preview and animator workflow

The features below exist since 0.3.3 beta (Windows prerelease); stable 0.3.2 lacks them. Running inside Maya has not been verified ([what is verified](verification.en.md)).

Select **Man_Rig** as the Maya rig in Settings and process the take again. Studio displays the skinned character. The 3D view menu switches between the character, capture body, bones and character with bones. Disable “Follow character” to judge displacement and foot sliding against the floor.

With Man_Rig selected, “Download Maya scene (.ma)” saves the character geometry, original skin weights and baked animation; with Capture skeleton or a custom rig it downloads the capture skeleton (with a `FaceExpressions` node when expressions are enabled). Details: [Maya rigs](maya-rigs.en.md). The scene uses the export frame rate and integer keys from 1 to the frame count. The Maya button opens this prepared scene. BVH/FBX retain the capture skeleton. Reprocess older takes. Custom `.ma` rigs still require Maya; Studio does not interpret arbitrary Maya controllers, constraints or scripts.

Man_Rig has 65 joints and skinning, but no animator IK/FK controls. Retargeting respects the bind pose and jointOrient while retaining character bone lengths. Different proportions can change foot contacts and cause intersections. Studio uses simplified materials and cannot reconstruct missing textures. **Facial expressions:** with Full face and expressions enabled, 52 ARKit curves are keyed on the attributes of a `FaceExpressions` node in the scene. Man_Rig has no facial blend shapes, so the character's face does not move by itself: connect the `FaceExpressions` attributes to your own blendShape node (Connection Editor or expressions). [Facial expressions and hands](facial-expressions.en.md).

## Clip ranges and saved versions

Set inclusive In/Out frames below the video. Set In/Out use the current frame; the arrow buttons beside Play advance by one frame. The ↻ button loops the selected range. Camera views provide orbit, front, back and side directions with perspective projection.

Export selected range creates a separate ZIP with `capture.bvh`, skeletal `capture.ma`, `character.ma` when Man_Rig is prepared, and `clip.json` with frame range, FPS and duration. Check Include FBX to add a Blender-exported skeleton. In-place export removes horizontal root translation while preserving vertical motion, jumps and root rotation. Original video and animation remain unchanged; repeated exports receive unique filenames. The exported-clips list retains previous variants.

Completed outputs are saved under the take's `versions` folder before reprocessing. Previous animation versions can be downloaded from Studio. Archives contain finished animations, geometry and required preview binary data; source video and model environments are not duplicated. Extract and open `.ma` in Maya or BVH in a 3D editor. A version archive cannot rerun recognition without the original video. Versions are not automatically deleted and consume disk space. Older results without recorded processing options mark those options as unverified.

## Development priorities

1. Target-character foot contact review, editable support intervals and floor height; IK corrections must preserve jumps and blend into free motion. Existing capture foot locking does not replace this step.
2. A verified HumanIK definition and control rig, followed by [Bake To Control Rig](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-CharacterAnimation/files/GUID-1704AD41-8435-4AD4-AF29-43EF13803EAC.htm). This is additional rigging work, not a feature of the current asset.
3. Preserve original takes/settings and keep corrections in separate versions. Maya [animation layers](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Animation/files/GUID-5C202CB8-EB3C-4ADE-B203-5F93A9FD9104.htm) support non-destructive adjustments; Autodesk documents their use for [mocap cleanup](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Animation/files/GUID-C97668C6-6D9C-49E2-BF3F-FC88BE9269D1.htm).
4. Before/after comparison and clip assembly. In/Out ranges, segment looping, frame-step buttons and fixed views are available. Key reduction should require an explicit error tolerance and retain the original dense animation.
5. Expose missing/low-confidence hand intervals and review stabilization on fast gestures. Invisible fingers should not be presented as confidently measured motion.

These are development priorities, not implemented-feature claims.

## Verification

Tests check real geometry, all skin influences (including six weights per vertex), bind-pose reconstruction, preview quaternion/Maya rotation agreement, Maya YXZ rotation order and integer keys. A saved real GEM-X result from 25 FPS video was retargeted at 120 FPS and viewed in Studio. The native macOS ARM64 package is tested after extraction with its bundled Python. Actual Maya scene loading, Windows GPU inference and SAM-Body4D require separate tests in their respective environments.

### Maya correction preparation

After processing with Man_Rig, download the character `.ma` and **Maya finishing
tools (.py)**. Clip exports include `character.maya-tools.py` too. Open the character
scene, open the Python file in **Script Editor → Python**, then execute it. The panel
checks scene FPS and off-grid keys, offers an explicit additive correction-layer
button, and selects feet, wrists or fingers. Opening the scene executes no scripts.
All expected joints must be present and unambiguous; multiple matching characters
are rejected. No original keys are rebaked, and the scene is not automatically saved.
Keep `MoCapGate_Corrections` selected when keying; use **Save As** for edited work.
Undo removes layer creation. Editing uses joints, not IK/FK controllers. A different
scene FPS is reported without retiming existing edits. Actual Maya runtime testing
remains necessary.

### Motion review, comparison and queue

Motion review marks candidate rotation/root-trajectory jumps. Select a marker or
use its arrows to seek; orange ticks appear on the timeline. These are heuristics,
not model confidence: legitimate fast gestures may be flagged. Missing detections
are marked only when observation data exists. Up to 1000 candidates are displayed.

Compare recognition creates a separate GEM-X/GVHMR take from the source video and
queues it without changing the original. Select a completed take to compare its
skeleton. Playback aligns time from video start, including different export FPS.
Check subject identity and start time yourself: equal participant IDs in independent
runs do not guarantee the same subject. The UI reports when the shorter take ends.

Enable Each video becomes a separate queued take for batch import with a local
backend. Takes join the Processing queue, which starts automatically. Jobs run sequentially; failures
allow the next job to proceed. Pause lets the active job finish. Removing a queue
entry does not delete its take. Queue records persist locally and require explicit
resume after restart. Processing does not continue with Studio closed.

### Character profiles and readiness checks

In Settings, upload a local Maya `.ma` or enter its path. Name the profile, open a
processed take, then Match familiar joints. Joint declarations are read as text;
the scene is never executed during matching. Edit the source-to-target JSON mapping
for custom names. Scale affects root translation rather than bone lengths; yaw
sets orientation around Y. Save the profile and Use profile.

Profiles affect **Open in Maya**, where joint transfer and baking run. The downloaded
prepared `.ma` and Studio preview still use Man_Rig. No profile restores regular rig
settings. Each Maya transfer uses a new output scene filename. Arbitrary IK/FK
controllers are unsupported, and real Maya runtime verification remains necessary.

Models & tools has two different checks. Check the computer (the setup wizard) inspects the system before installation: OS, memory, disk, driver, WSL, network ([setup wizard](setup-wizard.en.md)). Check system readiness inspects installed components: it detects tools and configured environments.
For configured GVHMR/GEM-X Python runtimes it also probes PyTorch import and CUDA
availability. Error details remain visible. Environment detection alone does not
prove inference works; complete verification with a short video. Maya is optional.

## Other features in brief

### Take library

Takes are listed newest first by creation date. At the top: search (name, model, project, tags, notes), a project filter (All projects) and status chips. Each take has a **Project, tags and notes** block: a project with suggestions from existing ones, comma-separated tags and notes. New takes go to the currently open project. Downloads are named after the current take name (renaming updates them); a take without a name uses the original file name.

### Process as a new take

**Process as a new take** creates a separate take from the same video with the chosen model (GEM-X · SOMA, GVHMR · this PC, GVHMR · Colab) and the settings currently in the form. The original take is untouched. GEM-X needs a video: a take holding only a GVHMR result cannot be processed with GEM-X.

### Batch export

**Select several for export**: tick completed takes and click Unreal, Unity, GLB or FBX (with the Root motion option). Takes are exported one by one; for multi-person takes all participants go into one file. Blender is required.

### BVH import

Drop a `.bvh` (Rokoko, Xsens, older takes) to create a take with the "bvh-file" backend. Smoothing, foot locking, the Maya scene, Man_Rig, engine export and clips work without a recognition model. For a non-humanoid skeleton Man_Rig is skipped with a message.

### Engine export

The For game engines block: Unreal · FBX, Unity · FBX, glTF · GLB, Live Link Face · CSV; root motion and All participants in one file. Unreal names are a subset of the UE5 Mannequin; engine import is not verified. [Engine export](engines.en.md).

### Your own character

Upload character (.fbx, .glb, .gltf, .blend) → Transfer animation: Mixamo, UE, Unity, Rigify, CC, Daz and VRoid bones are matched automatically; expressions drive ARKit-named shape keys. Verified only by Blender reimport on test rigs. [Your own character](own-character.en.md).

### Game clips

Export selected range with Seamless loop (the last ~0.3 s blend into the start) and Root bone (root motion). [Clips and fixes](clips-and-fixes.en.md).

### Fixing frames and versions

Fix these frames replaces the In–Out range with smooth interpolation of its neighbours; before that, and before Process again, the result is saved to Previous animation versions. [Clips and fixes](clips-and-fixes.en.md#fixing-frames).

### Smoothing and foot locking

Smooth body jitter and Smooth finger jitter range 0…1 with an adaptive filter: jitter is removed while fast moves stay sharp. Pin the feet to the floor: for GEM-X, foot contacts plus leg IK, with sliding reported before → after; for GVHMR, root correction. GEM-X Accurate mode additionally pins feet with GEM-X post-processing.

### Hands on GVHMR takes

With hands and fingers enabled, a GVHMR take takes its wrists and fingers from GEM-X when GEM-X is installed (setting `gvhmr_hands`: `auto` — default, `gemx`, `mediapipe`). GEM-X runs on the same video (Fast quality, same recognition FPS / resolution / parts; its result is cached in the take as for GEM-X takes), people are matched by their 2D boxes over time, and the GEM-X hand pose relative to the forearm is transferred onto the GVHMR skeleton; the GVHMR body and feet are kept. Wrist and finger limits and finger stabilisation still apply. People GEM-X did not find, frames where GEM-X lost the person (with a 0.25 s fade) and any GEM-X failure fall back to MediaPipe hands; the log shows `INFO [MoCapGate] hands: …` lines with the matches.

### Queue and model comparison

Takes run one at a time; adding a take starts the queue. Pause queue lets the current take finish; after restarting Studio, resume interrupted takes with Start queue. Compare recognition is described above.

### Setup wizard

Models & tools → Installation, step by step: Check the computer, Install everything recommended, Open the demo take, Support report. [Setup wizard](setup-wizard.en.md).

## Thumbnails and takes waiting for Colab

Takes with a video show a frame thumbnail in the list (created in the background for older takes). A take waiting
for a Colab result has **Show the video file** and **Process on this PC instead** — a new take from the same video
with GEM-X or GVHMR. If uploaded files have not become a take yet, Studio asks before you leave the import.
