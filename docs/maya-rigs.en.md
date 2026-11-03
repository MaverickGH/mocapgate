# Maya rigs

[Русский](maya-rigs.ru.md) · [Animator workflow](animator-workflow.en.md) · [Models and Maya](models-and-maya.en.md)

Since 0.3.3 beta (Windows prerelease). **Running inside Maya has not been verified**: the `.ma` format, keys
and rotation maths are covered by unit tests, but opening the scene, transfer and the finishing tools in Maya
itself are not ([what is verified](verification.en.md)).

## Three options

Choose under Settings → **Maya character**.

| Option | Download Maya scene (.ma) contains | Open character in Maya |
|---|---|---|
| **Man_Rig** (default) | the Man_Rig character: geometry, skinning, baked animation | the same prepared scene |
| **Capture skeleton** | the recognized skeleton with animation | the skeleton scene |
| **Custom Maya rig** (`.ma`) | the recognized skeleton | Maya transfers the motion to your rig and bakes joints; a separate scene file is saved |

In every case keys sit on integer frames 1…N and the scene FPS equals the export FPS. With expressions
enabled the scene has a `FaceExpressions` node with 52 ARKit attributes. FBX always contains the capture
skeleton. Multi-person takes get a scene (and a Man_Rig) per participant.

**Man_Rig** has 65 joints and skinning, no IK/FK controls and no facial blend shapes: to move a face, connect
the `FaceExpressions` attributes to your own blendShape node. The rig was supplied by the user with permission
to distribute; its author and source are not identified (`assets/rigs/README.md`).

## Rig profiles

Settings → **Maya character profiles** — for custom rigs with unusual names:

1. Upload a `.ma` or enter its local path, and set a **Name**.
2. Open a processed take and click **Match familiar joints**: names are read as text; the scene is never executed.
3. Edit **JSON: source → character joint** for unmatched bones.
4. **Trajectory scale** changes root travel, not bone lengths; **Yaw (Y rotation), °** sets the direction.
5. **Save profile** → **Use profile**.

A profile applies only to **Open character in Maya**. The downloaded `.ma` and the Studio preview are
unchanged. Arbitrary Maya controllers, constraints and scripts are not interpreted.

## Finishing tools and correction layer

Download **Maya finishing tools (.py)** (in a clip archive: `character.maya-tools.py`), open the scene, then
open the file in **Script Editor → Python** and run it. The panel checks FPS and off-grid keys, selects feet,
wrists or fingers, and its **Create additive correction layer** button creates the additive layer
`MoCapGate_Corrections`. Original keys are not rebaked; keep the layer selected when keying and save edits
with **Save As**. Opening the scene runs nothing: only you execute the script. Edits use joints, not IK/FK
controls.
