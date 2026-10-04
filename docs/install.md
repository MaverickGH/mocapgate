# Установка MoCapGate Studio

## 1. Приложение

### Где скачать

Репозиторий исходников открыт. Готовые пакеты находятся в
[app-releases — MoCapGate 0.3.1](https://github.com/MaverickGH/app-releases/releases/tag/mocapgate-v0.3.1).
Выберите quickstart для своей платформы или переносной ZIP. Для использования
пакета не нужны Git, Rust или Node; интернет нужен при первом скачивании
Python и моделей. Полная инструкция: [Русский](../README.md) · [English](../README.en.md).

### Быстрый старт на macOS

Apple Silicon (M1 и новее): пакет `*-macos-arm64-quickstart.zip`.
Mac с Intel: пакет `*-macos-x64-quickstart.zip`.
Распакуйте архив и откройте `INSTALL.command`. Он ставит приложение в
`~/Applications`, uv, отдельный Python 3.12 с numpy и MediaPipe heavy.
Нужны права обычного пользователя, администратор не требуется.
Проверка из терминала: `bash scripts/setup_macos.sh --plan`.
Для подготовки без открытия окна: `--skip-launch`.
Для полной поверхности добавьте `--smplx-model /полный/путь/SMPLX_NEUTRAL.npz`:
создаётся отдельный CPU torch/smplx runtime. GVHMR на Mac доступен через Colab;
локальный движок GVHMR требует NVIDIA CUDA.

Имена костей тела и пальцев следуют соглашениям Mixamo. Префикс `mixamorig:`
включается отдельно в настройках дубля; после изменения нужен повторный экспорт.
`…HandIndex4` и другие `…4`, `HeadTop_End`, `Left/RightToe_End` — фиксированные
окончания цепочек. Обычный скелет с пальцами содержит 65 именованных суставов;
SMPL-X с челюстью и глазами — 68 (55 моделируемых и 13 окончаний).
«Структура скелета» под 3D-просмотром показывает настоящую иерархию выбранного ID.
Совпадение имён не заменяет ретаргет на пропорции вашего персонажа.

### Быстрый старт на Windows

Самый простой вариант: скачать `*-windows-quickstart.zip` из [публичного релиза](https://github.com/MaverickGH/app-releases/releases/tag/mocapgate-v0.3.1),
распаковать и дважды нажать **INSTALL.cmd**. Внутри уже есть EXE и скрипт
подготовки; собирать исходники не нужно. Контрольные суммы — в `SHA256SUMS.txt`.

Для ручной установки используйте EXE из quickstart вместе со скриптами того же
пакета (или установщик из соответствующей сборки CI). В PowerShell из распакованной папки:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1 -InstallerPath "C:\Downloads\MoCapGate Studio_0.3.1_x64-setup.exe"
```

Скрипт устанавливает uv с официального astral.sh, создаёт отдельный Python 3.12
с numpy, запускает установщик текущего пользователя, устанавливает MediaPipe
и модель heavy, затем открывает EXE. Администратор и ручной pip не нужны.
Первый запуск требует интернета и несколько минут; повторный использует кэш.
Без `-InstallerPath` запускается уже установленный EXE либо переносная версия
в браузере. Можно также дважды нажать `scripts/start_windows.cmd`.
Проверить план без изменений: `-Plan`; подготовить без открытия окна: `-SkipLaunch`.

Для поверхности тела на CPU (дополнительно несколько сотен МБ) скачайте свою
`SMPLX_NEUTRAL.npz` на сайте SMPL-X и добавьте:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1 -FullAvatar -SmplxModel "C:\Models\SMPLX_NEUTRAL.npz"
```

После этого включите **Полная модель SMPL-X**, **Пальцы рук** и **Полное лицо**
в настройках дубля. Этот вариант ставит CPU torch/smplx для поверхности;
GVHMR на NVIDIA устанавливается отдельно по разделу ниже. Если окружение GVHMR
уже указано, скрипт сохраняет его настройку. Blender нужен для FBX, FFmpeg —
для перекодирования записей и локального GVHMR; ссылки есть в «Статус и ИИ».
Записи, настройки и лицензированные модели пользователей в Git не загружаются.

| Система | Опубликованные пакеты 0.3.1 (`MaverickGH/app-releases`) |
|---|---|
| macOS (Apple Silicon) | `MoCapGate-0.3.1-macos-arm64-quickstart.zip` или DMG `aarch64` |
| macOS (Intel) | `MoCapGate-0.3.1-macos-x64-quickstart.zip` или DMG `x64` |
| Windows 10/11 x64 | `MoCapGate-0.3.1-windows-quickstart.zip` (EXE внутри) |
| Linux / любая ОС | `MoCapGate-0.3.1-portable.zip` |

EXE/MSI, DEB и AppImage поддерживаются сборочным workflow, но отдельными файлами
в этом публичном релизе не опубликованы.

Сборки пока без подписи: на macOS первый раз — правый клик по приложению → **Открыть**; на Windows —
**Подробнее → Выполнить в любом случае**.

Переносная версия (любая ОС, без установки): распаковать и выполнить `python3 mocapgate.py studio`.

## 2. Python 3.9+

Обычно уже есть. Если приложение пишет, что Python не найден, поставьте его с
[python.org](https://www.python.org/downloads/) (на Windows отметьте *Add python.exe to PATH*).
Через pip ничего ставить не нужно: ядро и сервер работают на стандартной библиотеке.

На Windows приложение также ищет Python в `%LOCALAPPDATA%\Programs\Python` и в папке
Python от uv (`%APPDATA%\uv\python` или `UV_PYTHON_INSTALL_DIR`), даже если его нет в PATH.
Для Python в другом месте можно задать `MOCAPGATE_PYTHON` — полный путь к `python.exe`.

## 3. Распознавание позы

- **MediaPipe на компьютере.** «Статус и ИИ» → MediaPipe → **Установить** (~1 ГБ, ставится в
  `~/.cache/mocapgate/mediapipe`, свой Python через [uv](https://docs.astral.sh/uv/getting-started/installation/)).
  Модели: lite (быстрая), full, heavy (точнее всех).
- **GVHMR в Colab — лучшее качество, без установки.** «Новый дубль» → GVHMR · Colab → **Открыть в Colab**
  (или скачать ноутбук и загрузить в Colab: *Файл → Загрузить блокнот*). Один раз нужна модель
  `SMPLX_NEUTRAL.npz` — бесплатная регистрация на [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de).
  Результат — `*_mocapgate.zip`, его перетаскивают в дубль.
- **GVHMR на своей видеокарте NVIDIA.** Установите GVHMR по [его инструкции](https://github.com/zju3dv/GVHMR/blob/main/docs/INSTALL.md),
  положите веса и `SMPLX_NEUTRAL.npz`, затем в «Настройках» укажите папку GVHMR и Python его окружения.

## 4. Экспорт

- **Blender 3.5+** ([blender.org](https://www.blender.org/download/)) — для FBX и кнопки «Открыть в Blender».
  BVH в Blender: *File → Import → Motion Capture (.bvh)*, Scale **0.01**.
- **Maya** — импорт FBX (плагин FBX включён по умолчанию), ретаргет через HumanIK. Если Maya найдена,
  у дубля появится «Открыть FBX в Maya».
- **ffmpeg** — желательно: записи с камеры превращаются в mp4 с ровной частотой; обязателен для локального GVHMR.

Что найдено, а чего нет, всегда видно в «Статус и ИИ» или командой `python3 mocapgate.py doctor`.

## Сборка установщиков

Новые сборки используют нативный пакет с CPython 3.12.13. Workflow
`.github/workflows/studio.yml` запускается вручную только в приватном зеркале
исходников; автоматическая публикация по тегу отключена. Подготовьте и проверьте
пакет по [инструкции](code-protection.ru.md), затем:

```bash
export MOCAPGATE_NATIVE_PACKAGE="$PWD/dist/native-package"
cd apps/studio/desktop
npm ci
npx tauri build
```

Нужны Node 20+, Rust stable, CPython 3.12.13 и зависимости из requirements-native.txt;
на Linux ещё `libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`.

На Windows также нужны Visual Studio Build Tools (или Visual Studio) с компонентом
**«Разработка классических приложений на C++»** и Windows SDK. Установка этих компонентов
требует прав администратора и свободного места на системном диске.
При переносе проекта с macOS выполните `npm ci` заново на Windows: папки `node_modules`
и `src-tauri/target` содержат файлы для исходной ОС и не заменяют Windows-сборку.

Windows-оболочка также ищет uv и ffmpeg в `%USERPROFILE%\.local\bin`:
инструменты в этой папке доступны приложению, даже если «Пуск» ещё не получил обновлённый PATH.
