# Сторонние компоненты · Third-party notices

Код MoCapGate — MIT (см. LICENSE). Ниже — что MoCapGate использует или скачивает по запросу пользователя.

| Компонент | Где | Лицензия |
|---|---|---|
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) (Pose Landmarker, Tasks Vision) | распознавание позы на компьютере и живая проверка камеры; ставится по кнопке | Apache-2.0 |
| [OpenCV](https://opencv.org) (opencv-python-headless) | чтение видео в компоненте MediaPipe | Apache-2.0 |
| [three.js](https://threejs.org) | 3D-просмотр BVH в Studio | MIT |
| [IBM Plex Sans](https://github.com/IBM/plex) | шрифт интерфейса | SIL OFL 1.1 (apps/studio/ui/fonts/LICENSE.txt) |
| [Tauri](https://tauri.app) | десктоп-оболочка | MIT / Apache-2.0 |
| [GVHMR](https://github.com/zju3dv/GVHMR) | лучший бэкенд позы — запускается в Colab или на своём GPU, в MoCapGate не входит | **только некоммерческое** (education, research, non-profit) |
| [SMPL-X](https://smpl-x.is.tue.mpg.de) | модель тела для GVHMR и точных костей — пользователь скачивает сам | **только некоммерческое** |
| [Sports2D demo](https://github.com/davidpagnon/Sports2D/blob/main/Sports2D/Demo/demo.mp4) | настоящее тестовое видео в `tests/fixtures/sports2d`, исходная лицензия сохранена рядом | BSD-3-Clause |

Использование GVHMR и модели SMPL-X регулируется их собственными условиями:
[GVHMR LICENSE](https://github.com/zju3dv/GVHMR/blob/main/LICENSE),
[SMPL-X model licence](https://smpl-x.is.tue.mpg.de/modellicense.html).
MIT-лицензия кода MoCapGate не заменяет эти условия; модель пользователь получает отдельно.

**English:** MoCapGate code is MIT. Third-party components retain their own licences.
GVHMR and the SMPL-X model have non-commercial restrictions; consult the linked
upstream terms. No licensed SMPL-X model is distributed in this repository or its packages.

Нативные пакеты дополнительно включают CPython и uv. Полные тексты лицензий
CPython и библиотек его standalone-сборки сохранены в `python-licenses`, uv —
в `uv-licenses` (MIT / Apache-2.0). Происхождение Python фиксируется в
`python-licenses/provenance.json`. Cython используется только при сборке;
тексты его Apache-2.0 лицензии и пояснение о правах на результат компиляции
также поставляются с пакетом в docs/licenses.
