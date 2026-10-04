# Выпуск MoCapGate на сайт

Тот же путь, что у VideoText и «Разборщика»: установщики — в публичный `MaverickGH/app-releases`
(тег `mocapgate-vX.Y.Z`), на сайте — программа в разделе «Программы» с кнопками «Скачать».

## 1. Сборки

Тег `vX.Y.Z` в этом репозитории → `.github/workflows/studio.yml` собирает всё и делает черновик релиза
`MaverickGH/mocapgate` с файлами и `SHA256SUMS.txt`. Репозиторий публичный — Actions бесплатны.

## 2. Файлы в app-releases

Сайт принимает ссылки на `.zip` и `.dmg` с именами из `[A-Za-z0-9._-]`. Берём из релиза:

| Платформа | Файл |
|---|---|
| macOS · Apple Silicon | `MoCapGate.Studio_X.Y.Z_aarch64.dmg` |
| macOS · Intel | `MoCapGate-X.Y.Z-macos-x64-quickstart.zip` |
| Windows 10/11 | `MoCapGate-X.Y.Z-windows-quickstart.zip` |
| Linux / любая ОС | `MoCapGate-X.Y.Z-portable.zip` |

```bash
V=0.3.1
gh release download v$V -R MaverickGH/mocapgate -D dist/site \
  -p "*_aarch64.dmg" -p "*-quickstart.zip" -p "*-portable.zip" -p "SHA256SUMS.txt"
gh release create mocapgate-v$V -R MaverickGH/app-releases \
  -t "MoCapGate $V — мокап из видео · motion capture from video" -F docs/site/release-notes.md dist/site/*
```

В README `app-releases` — блок приложения (шаблон ниже).

## 3. Программа на сайте

`docs/site/program.json` — поля админ-API (`/admin/programs`, направление «3D и геймдев-пайплайн»,
`game-3d-pipeline`). Вставить в админку как черновик, проверить кнопки «Скачать», затем «Опубликовать».
Ссылки модулей m2–m5 ведут на `app-releases/releases/download/mocapgate-vX.Y.Z/...` — при новой версии
обновить номер.

Обложка: `docs/site/mocapgate-cover-v1.webp` (1600×900, ImageGen в стиле семейства Programs; промпт — в
`platform/docs/mocapgate-program-art.md` сайта; запасной рендер Blender — `mocapgate-cover-blender.webp`,
`scripts/render_cover.py`) →
`platform/public/assets/programs/mocapgate-cover-v1.webp`, slug `mocapgate` в `PROGRAM_ART`
(`components/programs/ProgramsHub.tsx`) или `cover_url: /assets/programs/mocapgate-cover-v1.webp`.

## Блок для README app-releases

```markdown
### MoCapGate — мокап из видео · motion capture from video
Снимите человека на телефон или веб-камеру — анимация скелета BVH/FBX для Blender, Maya и движков.
Film a person — get a BVH/FBX skeleton animation for Blender, Maya and game engines.
- **macOS (DMG, Apple Silicon)**, **macOS Intel и Windows (быстрый старт ZIP)**, **Linux / любая ОС (переносной ZIP)**
  → [релиз / release `mocapgate-v0.3.1`](../../releases/tag/mocapgate-v0.3.1)
- Исходники / source (MIT): [MaverickGH/mocapgate](https://github.com/MaverickGH/mocapgate).
  GVHMR и SMPL-X — только некоммерческое использование / non-commercial only.
```
