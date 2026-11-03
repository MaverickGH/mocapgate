# Multiple people

[Русский](multiple-people.md)

**Current status:** group capture is experimental. A two-person ID check on real Sports2D footage passed;
it is not a 3D accuracy check of every joint: [test report](multiple-people-real-test.md) (Russian).

GEM-X and GVHMR process several people on a shared timeline. The take option **Maximum people** ranges
from 1 to 8, default 4. It limits simultaneous detections; it does not promise accuracy for eight people in
a crowd. With several people, **All participants** is selected by default and every visible skeleton is shown
in 2D and 3D. "Participant ID 2" means the second participant, not a number of people to detect. Select an ID
for its own report, download and Blender/Maya actions. Make FBX exports every participant; engine export can
put everyone into one file (**All participants in one file**).

With several people, files are named `<name>_person_<ID>.bvh`, `.ma` and `.fbx`. A single person keeps the
plain file name. All files share FPS and length; outside the observed interval the pose is held and the viewer
hides the participant. Short gaps are interpolated. Older single-person takes still open.

## GEM-X

Since 0.3.3 beta. One **YOLOX + ByteTrack** pass over the whole video finds people and links them into tracks.
A participant is a stable track of at least **0.25 s** (configurable); tracks are ranked by total box area and
the first Maximum people are kept. 2D keypoints, SAM 3D Body features and GEM-X motion are computed separately
for each participant.

- **Separate animation per person:** BVH, a Maya scene and, when Man_Rig is the selected rig, a Man_Rig per
  participant; with expressions enabled, separate 52 curves.
- **Shared scene:** each position comes from GEM-X camera-space parameters with gravity-aligned vertical; everyone
  stands on a shared floor at **Y = 0** (from the feet). The take shows the camera height above the floor.
- **Take options:** Person detection confidence (lower finds small or partly hidden people, and more false ones),
  Shortest participant, s (shorter appearances such as passers-by or edge flicker are ignored), Remember a lost
  person, frames (how long a person may be hidden and keep the same ID; 30 ≈ 1 s).

Relative placement and contacts between people are approximate. Multi-person GEM-X has been tested less than
single-person capture: start with one person ([what is verified](verification.en.md)).

## GVHMR

Local GVHMR uses separate YOLO tracks and processes them sequentially on one GPU. Each world trajectory is
estimated independently; exact relative positions and interactions are not guaranteed. Colab exports a
`mocapgate.scene/1` scene and per-person BVH files in one ZIP; importing the ZIP/JSON keeps every ID. A full run
needs a licensed `SMPLX_NEUTRAL.npz`. On Windows, two-person preprocessing was checked on a GTX 1080; IDs shorter
than 0.25 s are dropped, and a full stationary-camera run with the user's model produced two participants,
BVH/FBX and 230 frames on the same video. This is not a 3D accuracy check of every joint.

## MediaPipe (legacy path)

MediaPipe is no longer offered as a body model in Studio; the path remains in the CLI (`--backend mediapipe`)
and for older takes. There, people are detected by a separate EfficientDet Lite2 (~24 MB) over the full frame
and overlapping tiles, pose is recognized inside each box, and IDs are linked by position, size and smoothed
velocity. 3D placement of participants is approximate.

## Common limits

After a long absence a person receives a new ID. Full occlusion and similar poses can swap IDs; there is no
appearance-based re-identification. Keep people apart and film the whole body. A single camera cannot guarantee
exact depth or contact between people.

## Command line

```powershell
python mocapgate.py new duet.mp4 --backend gemx-local --max-people 4
python mocapgate.py new duet.mp4 --backend gvhmr-local --max-people 2
python mocapgate.py process <take-folder> --fbx
```

Direct GVHMR scene import also writes a BVH per participant:

```powershell
python mocapgate.py scene.mocapgate.json -o duet.bvh
```

The short `mocapgate.py video.mp4 -o out.bvh` form uses the legacy MediaPipe path and copies only the primary
BVH. Use Studio or `new` to control groups and access every result.

## GVHMR: several people in one scene (0.3.3 beta)

GVHMR starts each person's trajectory at the origin with its own heading — previously everyone stood in one spot in 3D.
Now participants are moved into the first person's world through the shared static camera (as with GEM-X): positions
and headings as in the video, common floor (Y = 0). People without camera data stay as they were (logged).
Not applied with “Root motion: in place”.
