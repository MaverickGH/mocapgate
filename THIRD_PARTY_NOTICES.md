# Сторонние компоненты · Third-party notices

Текущий код MoCapGate — Apache-2.0 (см. LICENSE). Ниже — что MoCapGate использует или скачивает по запросу пользователя.

| Компонент | Где | Лицензия |
|---|---|---|
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) (Hand / Face / Pose Landmarker, Tasks Vision JS) | помощник: детали кистей и лица, 52 коэффициента выражений с именами ARKit, живая проверка камеры; прежний CLI-путь тела. Модели Landmarker включены в `assets/models/mediapipe`; Tasks Vision JS — в `apps/studio/ui/vendor` или с CDN | Apache-2.0 |
| [OpenCV](https://opencv.org) (opencv-python-headless) | чтение видео в компоненте MediaPipe | Apache-2.0 |
| [three.js](https://threejs.org) (вкл. addons OrbitControls, BVHLoader) | 3D-просмотр в Studio | MIT |
| [IBM Plex Sans](https://github.com/IBM/plex) | шрифт интерфейса | SIL OFL 1.1 (apps/studio/ui/fonts/LICENSE.txt) |
| [Tauri](https://tauri.app) | десктоп-оболочка | MIT / Apache-2.0 |
| [Epic OpenRigLogic](https://github.com/EpicGames/OpenRigLogic) | экспериментальные DNA/RigLogic утилиты Windows; отдельный LICENSE в tools/metahuman/runtime | MIT; персонажи Fab предоставляются отдельно по своим условиям |
| [GVHMR](https://github.com/zju3dv/GVHMR) | одна из моделей тела — запускается в Colab или на своём GPU, в MoCapGate не входит | **только некоммерческое** (education, research, non-profit) |
| [GEM-X](https://github.com/NVlabs/GEM-X) | модель тела; ставится по кнопке в отдельное окружение, в MoCapGate не входит | код Apache-2.0; веса — [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) |
| [SOMA-X](https://github.com/NVlabs/SOMA-X) | параметрическое тело для GEM-X (подмодуль) | Apache-2.0; сторонние модели — свои условия |
| [SAM 3D Body](https://github.com/facebookresearch/sam-3d-body) | признаки тела для GEM-X (скачиваются загрузчиком GEM-X) | [SAM License](https://github.com/facebookresearch/sam-3d-body/blob/main/LICENSE) (Meta) |
| [MHR](https://github.com/facebookresearch/MHR) | модель тела, используемая GEM-X | Apache-2.0 |
| [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) (ONNX от [MMPose](https://github.com/open-mmlab/mmpose)) | обнаружение людей для GEM-X | код Apache-2.0; веса — см. upstream |
| [ViTPose](https://github.com/ViTAE-Transformer/ViTPose) | 2D-точки для GEM-X (ONNX из загрузчика GEM-X) | код Apache-2.0; веса — см. upstream |
| [ByteTrack](https://github.com/FoundationVision/ByteTrack) | трекинг людей в GEM-X | MIT |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | выполнение ONNX-моделей GEM-X | MIT |
| [PyTorch](https://github.com/pytorch/pytorch), torchvision | окружения GEM-X и CPU-инструментов SMPL-X | BSD-3-Clause |
| [SMPL-X](https://smpl-x.is.tue.mpg.de) | модель тела для GVHMR и точных костей — пользователь скачивает сам | **только некоммерческое** |
| [Sports2D demo](https://github.com/davidpagnon/Sports2D/blob/main/Sports2D/Demo/demo.mp4) | тестовое видео и результаты в `tests/fixtures/sports2d` и демо-дубль в `examples/sports2d`; исходная лицензия сохранена рядом в обеих папках | BSD-3-Clause |

Веса моделей могут иметь условия, отличные от лицензии их кода (GEM-X, SAM 3D Body, YOLOX, ViTPose, GVHMR).
Закреплённые версии и места хранения: [docs/models-licences.ru.md](docs/models-licences.ru.md) ·
[English](docs/models-licences.en.md).

`samples/make_smpl_walk.py` создаёт `samples/smpl_walk.json` процедурно (синтетическая ходьба для проверки
конвертера); это не данные захвата и не модель SMPL/SMPL-X.

Использование GVHMR и модели SMPL-X регулируется их собственными условиями:
[GVHMR LICENSE](https://github.com/zju3dv/GVHMR/blob/main/LICENSE),
[SMPL-X model licence](https://smpl-x.is.tue.mpg.de/modellicense.html).
Apache-2.0 лицензия кода MoCapGate не заменяет эти условия; модель пользователь получает отдельно.

**English:** Current MoCapGate code is Apache-2.0. Third-party components retain their own licences.
GVHMR and the SMPL-X model have non-commercial restrictions; consult the linked
upstream terms. No licensed SMPL-X model is distributed in this repository or its packages.

Нативные пакеты дополнительно включают CPython и uv. Полные тексты лицензий
CPython и библиотек его standalone-сборки сохранены в `python-licenses`, uv —
в `uv-licenses` (MIT / Apache-2.0). Происхождение Python фиксируется в
`python-licenses/provenance.json`. Cython используется только при сборке;
тексты его Apache-2.0 лицензии и пояснение о правах на результат компиляции
также поставляются с пакетом в docs/licenses.

Установщик инструментов загружает Blender 4.5 LTS (GNU GPL, https://www.blender.org/about/license/) и FFmpeg из платформенного wheel imageio-ffmpeg 0.6.0 (BSD-2-Clause для обёртки; FFmpeg сохраняет LGPL/GPL в зависимости от сборки, https://ffmpeg.org/legal.html). Файлы лицензий wheel сохраняются рядом с установленным FFmpeg; лицензии Blender остаются в его дистрибутиве. Они скачиваются по действию пользователя и не включены в native-пакет.

The tools installer downloads Blender 4.5 LTS (GNU GPL) and the platform FFmpeg binary from imageio-ffmpeg 0.6.0. Wrapper and binary licences are separate; installed distributions retain their notices. No StyleGate source code is included.

Резервные веса GVHMR: [camenduru/GVHMR](https://huggingface.co/camenduru/GVHMR/tree/21b32d5389e2e59c0737d4c4095bbc0b8c23f66b), закреплённая версия зеркала, используемого публичным демо. Это стороннее зеркало; размер и SHA-256 закреплены в установщике. Права на модели и ограничения GVHMR сохраняются; файлы скачиваются только в пользовательское окружение после принятия условий. SMPL-X с этого зеркала не загружается.

Fallback checkpoints come from a pinned third-party camenduru/GVHMR mirror; their sizes and SHA-256 digests are recorded in the installer. Upstream model terms remain applicable. Checkpoints are downloaded into the user's managed environment after model-term acceptance; SMPL-X is still obtained separately.

Для ffprobe установщик использует отдельные платформенные сборки FFmpeg: Gyan (Windows), BtbN (Linux), OSXExperts (macOS ARM64/Intel). Архив поставщика сохраняется в пользовательской папке инструментов; перед установкой проверяется SHA-256. FFprobe сохраняет условия соответствующей сборки FFmpeg, см. https://ffmpeg.org/legal.html. Эти двоичные файлы не входят в дистрибутив Studio.

[GEM-X](https://github.com/NVlabs/GEM-X) и [SOMA-X](https://github.com/NVlabs/SOMA-X): Apache-2.0; запускаются в отдельном пользовательском окружении. GEM-X закреплён на `32992550dba114c62243fb55e361311972dce8f9`; подмодули и собственные уведомления upstream сохраняются. Модели скачиваются в окружение пользователя, не включаются в Studio; условия сторонних моделей сохраняются.

`assets/rigs/Man_Rig.ma`: пользователь предоставил риг и разрешил распространение 2026-10-07. Автор и исходный URL не указаны; MoCapGate не объявляет риг своей работой или лицензированным Apache-2.0. Подробности — `assets/rigs/README.md`.

Native-пакеты включают неизменённые Google MediaPipe Pose Landmarker Heavy,
Hand Landmarker и Face Landmarker (около 40 МиБ). Apache-2.0 тексты лицензии,
авторство Google, ссылки на model cards и закреплённые исходные URL сохранены
в `assets/models/mediapipe`. `manifest.json` содержит размеры и SHA-256;
при переносе моделей в пользовательский кэш приложение проверяет целостность.
Это разрешённые к распространению тестовые модели; SMPL-X, MetaHuman и
закрытые SAM checkpoints в данный набор не входят.

## Blender-скрипты · Blender scripts

Скрипты MoCapGate для Blender (`core/blender_io.py`, `core/blender_export.py`, `core/blender_retarget.py`,
`core/engine_export.py`) выполняются внутри установленного пользователем Blender (GNU GPL) как отдельной
программы; MoCapGate не компонуется с Blender и не распространяет его в пакетах.
MoCapGate's Blender scripts are executed inside the user's own Blender (GNU GPL) as a separate program;
MoCapGate does not link with or bundle Blender.

## Совместимость и товарные знаки · Interoperability and trademarks

Для совместимости MoCapGate использует общеизвестные соглашения об именах: кости UE5 Mannequin
(`pelvis`, `spine_01`…), имена 52 коэффициентов выражений ARKit (`jawOpen`…), соглашения Mixamo, Rigify,
Character Creator, Daz Genesis, VRM/VRoid, а также раскладку столбцов CSV приложения Live Link Face.
Никакие ресурсы, модели или код Epic Games, Apple, Adobe, Reallusion, Daz или pixiv в MoCapGate не входят.
Названия — товарные знаки их владельцев; их упоминание не означает одобрения или партнёрства.
For interoperability MoCapGate uses well-known naming conventions (UE5 Mannequin bone names, ARKit
expression names, Mixamo / Rigify / CC / Daz / VRoid conventions, the Live Link Face app's CSV column layout).
No Epic, Apple, Adobe or other vendor assets are included. Names are trademarks of their owners and imply
no endorsement.
