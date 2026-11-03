# Export for game engines

[Русский](engines.ru.md) · [README](../README.en.md) · [Verified / not verified](verification.en.md)

Open a processed take → Export → **For game engines**. FBX and GLB need Blender (install it under
Models & tools → Install everything recommended). Files are written into the take folder; download buttons
appear after each export.

| Button | File | Contents |
|---|---|---|
| **Unreal · FBX** | `<take>.unreal.fbx` | Bones renamed after the UE5 Mannequin (`pelvis`, `spine_01`, `thigh_l`, `hand_r`, `thumb_01_l`…), a `root` bone at the origin above `pelvis`. Centimetres, Y up / −Z forward, no leaf bones |
| **Unity · FBX** | `<take>.unity.fbx` | Mixamo-style names without the `mixamorig:` prefix for Humanoid auto-mapping; scale baked into transforms |
| **glTF · GLB** | `<take>.glb` | Metres, Y up, skeletal animation and morph-weight (expression) animation |
| **Live Link Face · CSV** | `<take>.livelink.csv` | Facial curves of the selected participant only; the button appears when the take has facial curves |

## Options

- **Root motion (a separate root bone carries the travel)** — horizontal translation and yaw move from the pelvis
  to the root bone; the pelvis keeps height, tilt and the remainder. The Unreal export always has a `root` bone;
  for Unity this option adds a `Root` bone above `Hips`.
- **All participants in one file** — shown when the take has more than one person. Each participant is a separate
  armature placed as in the BVH. The file gets an `_all` suffix.
- **Facial expressions.** When a participant has facial curves ([details](facial-expressions.en.md)), FBX and GLB get
  a helper mesh `FaceExpressions` parented to the head bone with 52 ARKit-named blend shapes and their animation.

## More formats, camera and sound

- **Mixamo · FBX** — `mixamorig:` names, centimetres, an “Armature” object, like Mixamo downloads.
- **Cascadeur · FBX** — Mixamo names without the prefix, centimetres.
- **Blender · .blend** — a ready Blender scene: armatures, per-participant actions, face, the filming camera and sound on the timeline.
- **Filming camera** (matchmove) is included in FBX, GLB and .blend when solved: GEM-X — the shared scene camera,
  GVHMR — from the first participant. Static camera (one averaged pose), lens distortion ignored. `camera.json`
  (`mocapgate.camera/1`) is stored in the take; 3D has a “From the filming camera” view, Maya scenes get `CaptureCamera`.
  With “Root motion: in place” no camera is written — it would not match the animation.
- **Sound** from the video is kept as `audio.wav`: a `MoCapGateAudio` node in Maya scenes (from frame 1), a sound strip
  in .blend and in “Open in Blender”, a “Sound from the video (WAV)” button. Clips get `capture.wav`, trimmed to the
  range and sped up/slowed with “Speed ×” (no sound in a seamless loop).

## Unreal skeleton limits

Names follow the UE5 Mannequin only as a subset: MoCapGate has three spine joints, exported as `spine_01`,
`spine_03`, `spine_05`; there is no `spine_02` or `spine_04`. Twist bones (`upperarm_twist_01_l`…) exist only where
the source skeleton has them (GEM-X/SOMA). To drive Manny or another character, retarget with the IK Retargeter,
which maps chains by their start and end bones.

## Live Link Face CSV

The column layout follows recordings of the Live Link Face app (Timecode, BlendShapeCount, 52 ARKit curves, then
nine head and eye rotation columns). It is not an Epic specification. Head and eye rotations are not captured and
are written as zeros. Timecode has the form `HH:MM:SS:FF.mmm`, starts at zero, non-drop-frame.

## What is verified

The export is verified by re-importing into Blender 3.5, 4.2 and 5.2 (bones, frames, blend shapes). **Import into Unreal Engine and Unity, and the Live Link Face CSV in
Unreal/MetaHuman, are not verified.** Check scale, root motion and skeleton mapping in your own project.
