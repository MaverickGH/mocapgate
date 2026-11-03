# Модели и лицензии

[English](models-licences.en.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)

Что MoCapGate скачивает или использует, с закреплённой версией (если она задана в коде), лицензией и местом
хранения. Состояние на 2026-10-10. **Это не юридическая консультация:** перед коммерческим использованием
прочитайте условия по ссылкам. Код и веса одной модели часто имеют **разные** условия. «См. upstream» —
мы не смогли однозначно подтвердить условия.

`~/.cache/mocapgate` — папка компонентов (переопределяется `MOCAPGATE_COMPONENTS_HOME`). На Windows GEM-X и
GVHMR ставятся **внутрь WSL** (та же папка в домашнем каталоге пользователя Ubuntu). Папка настроек:
macOS `~/Library/Application Support/MoCapGate`, Windows `%APPDATA%\MoCapGate`, Linux `~/.config/mocapgate`.

## Модели тела

| Компонент | Источник | Версия / SHA | Лицензия | Коммерческое использование | Где хранится |
|---|---|---|---|---|---|
| GEM-X (код) | [NVlabs/GEM-X](https://github.com/NVlabs/GEM-X) | `32992550dba114c62243fb55e361311972dce8f9` (`scripts/setup_gemx.py`) | Apache-2.0 | да, по Apache-2.0 | `~/.cache/mocapgate/gemx` |
| Веса GEM-X (`gem_soma.ckpt`, `gem_denoiser.onnx` и др.) | через `gem.utils.hf_utils` закреплённой ревизии GEM-X | по ревизии кода | [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) (по README GEM-X) | см. лицензию | папка GEM-X, `inputs/` |
| SOMA-X | [NVlabs/SOMA-X](https://github.com/NVlabs/SOMA-X), подмодуль GEM-X | ревизия подмодуля; файлы проверяются по SHA-256 из LFS-указателей | Apache-2.0; сторонние модели — свои условия | код — да; см. upstream для ресурсов | `third_party/soma` в папке GEM-X |
| SAM 3D Body (`sam3d_body.ckpt`, `sam3db_backbone.onnx`) | [facebookresearch/sam-3d-body](https://github.com/facebookresearch/sam-3d-body) | по ревизии GEM-X | [SAM License](https://github.com/facebookresearch/sam-3d-body/blob/main/LICENSE) (Meta, собственные условия) | см. SAM License | папка GEM-X, `inputs/` |
| MHR (`mhr_model.pt`) | [facebookresearch/MHR](https://github.com/facebookresearch/MHR) | по ревизии GEM-X | Apache-2.0 | см. upstream | папка GEM-X, `inputs/mhr_data` |
| YOLOX (детектор людей, ONNX) | [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX); файл `yolox_x_8xb8-300e_humanart-a39d44ed` с download.openmmlab.com ([MMPose](https://github.com/open-mmlab/mmpose)) | URL закреплён в `scripts/setup_gemx.py` | код YOLOX и MMPose — Apache-2.0; веса — см. upstream | см. upstream | `~/.cache/rtmlib/hub/checkpoints` |
| ViTPose (ONNX) | [ViTPose](https://github.com/ViTAE-Transformer/ViTPose); ONNX — из загрузчика GEM-X | по ревизии GEM-X | код Apache-2.0; веса — см. upstream | см. upstream | папка GEM-X, `inputs/onnx` |
| ByteTrack (алгоритм в GEM-X) | [FoundationVision/ByteTrack](https://github.com/FoundationVision/ByteTrack) | — | MIT | да | в коде GEM-X |
| GVHMR (код) | [zju3dv/GVHMR](https://github.com/zju3dv/GVHMR) | `ee960bb6e2ea2d381aa97f08e9b71ef320b624b1` (`scripts/setup_gvhmr.py`) | [собственная, некоммерческая](https://github.com/zju3dv/GVHMR/blob/main/LICENSE) | **нет** | `~/.cache/mocapgate/gvhmr` |
| Веса GVHMR | Google Drive авторов; резервное зеркало [camenduru/GVHMR](https://huggingface.co/camenduru/GVHMR/tree/21b32d5389e2e59c0737d4c4095bbc0b8c23f66b) | зеркало `21b32d5389e2e59c0737d4c4095bbc0b8c23f66b`; размеры и SHA-256 закреплены | условия GVHMR | **нет** | папка GVHMR |
| SMPL-X | [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de), загружает пользователь | — | [некоммерческая](https://smpl-x.is.tue.mpg.de/modellicense.html) | **нет** | папка настроек `body_models/`, копия в GVHMR |

## Помощники и инструменты

| Компонент | Источник | Версия | Лицензия | Коммерческое использование | Где хранится |
|---|---|---|---|---|---|
| MediaPipe (Python) + OpenCV headless | PyPI | `mediapipe==0.10.21`, `opencv-python-headless==4.11.0.86` (`core/components.py`) | Apache-2.0 | да | `~/.cache/mocapgate/mediapipe` |
| Модели MediaPipe Pose Heavy, Hand, Face Landmarker | storage.googleapis.com/mediapipe-models | размеры и SHA-256 в `assets/models/mediapipe/manifest.json` | Apache-2.0 | да | в пакете `assets/models/mediapipe`, копия в `~/.cache/mocapgate/mediapipe` |
| MediaPipe Tasks Vision (JS, живая проверка) | npm `@mediapipe/tasks-vision` | версия в `apps/studio/server.py` | Apache-2.0 | да | `apps/studio/ui/vendor` или CDN |
| ONNX Runtime | PyPI | `onnxruntime-gpu 1.20.2` на Linux/WSL; `onnxruntime` на Mac | MIT | да | окружение GEM-X |
| PyTorch, torchvision | PyPI / download.pytorch.org | `torch 2.10.0`, `torchvision 0.25.0` (GEM-X); `torch 2.5.1` / `2.2.2` (CPU SMPL-X) | BSD-3-Clause | да | окружения моделей |
| smplx (Python-пакет) | PyPI | `0.1.28` | [некоммерческая (MPI)](https://github.com/vchoutas/smplx/blob/main/LICENSE) | **нет** | `~/.cache/mocapgate/smplx` |
| Blender | download.blender.org | 4.5 LTS | GPL | да (условия GPL) | `~/.cache/mocapgate/tools/blender` |
| FFmpeg | `imageio-ffmpeg 0.6.0` (обёртка BSD-2-Clause); ffprobe — сборки Gyan / BtbN / OSXExperts | версии закреплены в `core/managed_tools.py` | LGPL/GPL по сборке | см. [ffmpeg.org/legal](https://ffmpeg.org/legal.html) | `~/.cache/mocapgate/tools` |

Скрипты MoCapGate для Blender (`core/blender_*.py`, `core/engine_export.py`) выполняются внутри вашего Blender
как отдельная программа; MoCapGate с Blender не компонуется.
