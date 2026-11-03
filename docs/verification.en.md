# What is verified

[Русский](verification.md) · Status as of **2026-10-10**, versions 0.3.2 (stable) and 0.3.3 beta.

"Not verified" means no check was done or its result is unknown to us — not that the feature fails.
A successful check on one platform does not confirm the others.

| What | macOS ARM64 | Windows x64 | macOS Intel | Linux x64 |
|---|---|---|---|---|
| Native package and unit tests (`unittest`) | verified (unpacked package with its own Python) | beta.4/5 packages built and run by the user; unit tests on Windows not verified | not verified | not verified |
| GEM-X inference | verified: one person, locally (ONNX/CoreML); multiple people not verified | not verified | not supported (use Colab) | not verified |
| GVHMR inference on your own GPU | not supported (use Colab) | verified by user report (beta.4/5, WSL2, NVIDIA) | not supported | not verified |
| Hands and facial expressions (MediaPipe helper) | not verified on 0.3.3 beta; CSV/Maya/FBX export covered by unit tests | not verified | not verified | not verified |
| Blender export (FBX, Unreal/Unity/GLB) and retargeting onto your character | verified by reimport into Blender 3.5, 4.2, 5.2 on test rigs | not verified | not verified | not verified |
| Maya runtime (opening `.ma`, transfer, finishing tools) | not verified | not verified | not verified | not verified |
| Unreal / Unity import, Live Link Face in Unreal/MetaHuman | not verified | not verified | not verified | not verified |
| WSL stops when processing is cancelled | — | not verified | — | — |
| Installer on a clean Windows | — | not verified | — | — |
| Code signing | none (builds are unsigned) | none | none | none |
| Pose editing and foot contacts (layer, Apply) | verified (tests + UI, 2026-10-10) | not verified | not verified | not verified |
| Filming camera, sound, Mixamo/Cascadeur/.blend, IK pins | verified (Blender 3.5/4.2/5.2, tests, 2026-10-10) | not verified | not verified | not verified |

Also:

- Real Character Creator, Daz and VRoid characters have not been tested; automatic bone matching is tested on test rigs.
- The macOS ARM64 column does not confirm Windows, Intel macOS or Linux.
- 0.3.1 and frame-rate checks are in the [real-video report](multiple-people-real-test.md) (Russian) and [frame rates](video-fps.en.md); these are historical checks of the legacy MediaPipe path.

See also: [engine export](engines.en.md), [your own character](own-character.en.md), [facial expressions](facial-expressions.en.md), [native package verification](native-verification.md).
