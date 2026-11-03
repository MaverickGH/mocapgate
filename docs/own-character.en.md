# Retarget onto your own character

[Русский](own-character.ru.md) · [README](../README.en.md) · [Engine export](engines.en.md)

The **Your character** block under Export in a processed take. Blender is required.

1. **Upload character** — an `.fbx`, `.glb`, `.gltf` or `.blend` with a mesh and a skeleton. The file is copied into
   the app settings folder (`characters/`) and is available in every take.
2. Select a specific participant (not All participants) and the character in the list.
3. **Transfer animation**. The result is an FBX `<participant BVH>.<character>.fbx` in the take folder with mesh,
   skinning, animation and shape keys; a download button appears below the block.

## How bones are matched

The character's armature is the one with the most bones. Names are reduced to humanoid roles and matched
automatically for Mixamo, UE4/UE5, Unity/generic, Rigify (`DEF-…`), Character Creator / iClone (`CC_Base_…`),
Daz Genesis, VRM / VRoid (`J_Bip_…`) and 3ds Max Biped conventions. Left only matches left. Unmatched bones are
listed in the completion message.

The rest pose is aligned per bone: an A-pose character follows the source T-pose; differences below 15° are left
alone so the source anatomy is not copied. The hips follow the source scaled by leg length; the floor is the lowest
foot point. Facial curves ([details](facial-expressions.en.md)) drive the character's ARKit-named shape keys
(`jawOpen`, `eyeBlinkLeft`…) when they exist.

## Feet (foot IK)

On by default; `--no-foot-ik` on `core/blender_retarget.py` turns it off. Foot contacts are detected on the source:
ankle and toe low and nearly still (with hysteresis and a minimum duration of 0.1 s). During each contact the
character's foot is locked to one point (the mean over the contact) with a 0.2 s blend in and out; the point is the
source foot in the character's space, corrected for the rest-pose proportions (hip width, foot placement under the
hips, foot length, ankle height). Thigh and shin are set by an analytic two-bone IK with the knee in the source knee
plane; the foot keeps the source rotation. An unreachable target lowers the hips smoothly instead of overextending
the knee. Between contacts the plain rotation transfer is kept. The result line (`MOCAPGATE_RESULT`) reports
`foot_slide_cm`: the mean foot path per contact before and after, in centimetres. The math is in `core/leg_ik.py`.

For a custom mapping, the Blender script `core/blender_retarget.py` accepts `--map` (JSON
`{source: character bone}`); the UI has no field for it yet.

## What is verified

Only by re-importing the result into Blender 3.5, 4.2 and 5.2 on test rigs. **Real Character Creator, Daz and
VRoid models have not been tested**, nor has importing the result into Unreal/Unity. Foot IK was checked in Blender 3.5 on test
rigs with different leg and hip proportions (contact sliding 9 cm → 0), not on real characters. Check shoulders,
hands, feet and floor contacts: different proportions can cause intersections.
