# Models and licences

[Русский](models-licences.ru.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)

What MoCapGate downloads or uses, with the pinned version (where the code sets one), licence and storage
location. Status as of 2026-10-10. **This is not legal advice:** read the linked terms before commercial use.
Code and weights of the same model often have **different** terms. "See upstream" means we could not confirm
the terms unambiguously.

`~/.cache/mocapgate` is the components folder (override with `MOCAPGATE_COMPONENTS_HOME`). On Windows, GEM-X and
GVHMR are installed **inside WSL** (the same folder in the Ubuntu user's home). Settings folder: macOS
`~/Library/Application Support/MoCapGate`, Windows `%APPDATA%\MoCapGate`, Linux `~/.config/mocapgate`.

## Body models

| Component | Source | Version / SHA | Licence | Commercial use | Stored in |
|---|---|---|---|---|---|
| GEM-X (code) | [NVlabs/GEM-X](https://github.com/NVlabs/GEM-X) | `32992550dba114c62243fb55e361311972dce8f9` (`scripts/setup_gemx.py`) | Apache-2.0 | yes, under Apache-2.0 | `~/.cache/mocapgate/gemx` |
| GEM-X weights (`gem_soma.ckpt`, `gem_denoiser.onnx`, …) | via `gem.utils.hf_utils` of the pinned GEM-X revision | per code revision | [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) (per the GEM-X README) | see licence | GEM-X folder, `inputs/` |
| SOMA-X | [NVlabs/SOMA-X](https://github.com/NVlabs/SOMA-X), GEM-X submodule | submodule revision; files checked against SHA-256 from LFS pointers | Apache-2.0; third-party models keep their terms | code yes; see upstream for assets | `third_party/soma` in the GEM-X folder |
| SAM 3D Body (`sam3d_body.ckpt`, `sam3db_backbone.onnx`) | [facebookresearch/sam-3d-body](https://github.com/facebookresearch/sam-3d-body) | per GEM-X revision | [SAM License](https://github.com/facebookresearch/sam-3d-body/blob/main/LICENSE) (Meta, custom terms) | see SAM License | GEM-X folder, `inputs/` |
| MHR (`mhr_model.pt`) | [facebookresearch/MHR](https://github.com/facebookresearch/MHR) | per GEM-X revision | Apache-2.0 | see upstream | GEM-X folder, `inputs/mhr_data` |
| YOLOX (person detector, ONNX) | [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX); file `yolox_x_8xb8-300e_humanart-a39d44ed` from download.openmmlab.com ([MMPose](https://github.com/open-mmlab/mmpose)) | URL pinned in `scripts/setup_gemx.py` | YOLOX and MMPose code Apache-2.0; weights — see upstream | see upstream | `~/.cache/rtmlib/hub/checkpoints` |
| ViTPose (ONNX) | [ViTPose](https://github.com/ViTAE-Transformer/ViTPose); ONNX from the GEM-X downloader | per GEM-X revision | code Apache-2.0; weights — see upstream | see upstream | GEM-X folder, `inputs/onnx` |
| ByteTrack (algorithm in GEM-X) | [FoundationVision/ByteTrack](https://github.com/FoundationVision/ByteTrack) | — | MIT | yes | in GEM-X code |
| GVHMR (code) | [zju3dv/GVHMR](https://github.com/zju3dv/GVHMR) | `ee960bb6e2ea2d381aa97f08e9b71ef320b624b1` (`scripts/setup_gvhmr.py`) | [custom, non-commercial](https://github.com/zju3dv/GVHMR/blob/main/LICENSE) | **no** | `~/.cache/mocapgate/gvhmr` |
| GVHMR weights | authors' Google Drive; fallback mirror [camenduru/GVHMR](https://huggingface.co/camenduru/GVHMR/tree/21b32d5389e2e59c0737d4c4095bbc0b8c23f66b) | mirror `21b32d5389e2e59c0737d4c4095bbc0b8c23f66b`; sizes and SHA-256 pinned | GVHMR terms | **no** | GVHMR folder |
| SMPL-X | [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de), uploaded by the user | — | [non-commercial](https://smpl-x.is.tue.mpg.de/modellicense.html) | **no** | settings `body_models/`, copy in GVHMR |

## Helpers and tools

| Component | Source | Version | Licence | Commercial use | Stored in |
|---|---|---|---|---|---|
| MediaPipe (Python) + OpenCV headless | PyPI | `mediapipe==0.10.21`, `opencv-python-headless==4.11.0.86` (`core/components.py`) | Apache-2.0 | yes | `~/.cache/mocapgate/mediapipe` |
| MediaPipe Pose Heavy, Hand, Face Landmarker models | storage.googleapis.com/mediapipe-models | sizes and SHA-256 in `assets/models/mediapipe/manifest.json` | Apache-2.0 | yes | bundled `assets/models/mediapipe`, copied to `~/.cache/mocapgate/mediapipe` |
| MediaPipe Tasks Vision (JS, live check) | npm `@mediapipe/tasks-vision` | version in `apps/studio/server.py` | Apache-2.0 | yes | `apps/studio/ui/vendor` or CDN |
| ONNX Runtime | PyPI | `onnxruntime-gpu 1.20.2` on Linux/WSL; `onnxruntime` on Mac | MIT | yes | GEM-X environment |
| PyTorch, torchvision | PyPI / download.pytorch.org | `torch 2.10.0`, `torchvision 0.25.0` (GEM-X); `torch 2.5.1` / `2.2.2` (CPU SMPL-X) | BSD-3-Clause | yes | model environments |
| smplx (Python package) | PyPI | `0.1.28` | [non-commercial (MPI)](https://github.com/vchoutas/smplx/blob/main/LICENSE) | **no** | `~/.cache/mocapgate/smplx` |
| Blender | download.blender.org | 4.5 LTS | GPL | yes (GPL terms) | `~/.cache/mocapgate/tools/blender` |
| FFmpeg | `imageio-ffmpeg 0.6.0` (BSD-2-Clause wrapper); ffprobe from Gyan / BtbN / OSXExperts builds | pinned in `core/managed_tools.py` | LGPL/GPL per build | see [ffmpeg.org/legal](https://ffmpeg.org/legal.html) | `~/.cache/mocapgate/tools` |

MoCapGate's Blender scripts (`core/blender_*.py`, `core/engine_export.py`) run inside your Blender as a separate
program; MoCapGate is not linked with Blender.
