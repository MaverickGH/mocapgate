# Facial expressions and hands

[Русский](facial-expressions.ru.md) · [README](../README.en.md)

## Turning it on

In the take options enable **Full face and expressions** (GVHMR and GEM-X) and process the take. Faces are found by
the MediaPipe helper tracker on the source video, so it must be installed (Models & tools) and the take must contain
the video. A Colab result contains the body only: enable the option in Studio and click **Process again**.

**Hand fingers (BVH / FBX)** — MediaPipe hand capture for GVHMR: 21 points per hand, 30 finger bones in BVH/FBX.
With GEM-X, fingers, eyes and jaw are already part of the SOMA skeleton (77 joints). Small or hidden hands and faces
are skipped; the body quality score does not rate finger or expression accuracy.

## What you get

52 ARKit-named expression coefficients (`jawOpen`, `eyeBlinkLeft`…) are resampled to the export FPS; gaps are
filled between neighbouring frames that have a face.

| Where | What |
|---|---|
| `<take>.face.csv`, button **Facial expressions (52 curves, CSV)** | Frame, time and 52 curves per participant |
| Maya scene `.ma` | A `FaceExpressions` node with animated ARKit attributes; connect them to your character's blendShape |
| FBX and GLB (including [engine export](engines.en.md)) | A helper mesh `FaceExpressions` at the head bone with 52 blend shapes and their animation |
| Live Link Face · CSV | The same curves in the Live Link Face app's layout ([limits](engines.en.md#live-link-face-csv)) |
| [Your character](own-character.en.md) | Curves drive the character's ARKit-named shape keys |
| **Hands / face data (JSON)** | Raw observations: 478 face points, hand points and gaps |

Clips trim the expression curves to the same frames. **Man_Rig has no facial blend shapes**: its scene contains the
`FaceExpressions` node, but the character's face does not move until you connect the attributes to your own rig.

## Limits

Expressions from a single camera are approximate; head and eye rotations are not written to the CSV. Expressions
have not been verified in Unreal, MetaHuman or Maya ([status](verification.en.md)).
