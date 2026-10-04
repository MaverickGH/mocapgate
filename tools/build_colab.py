#!/usr/bin/env python3
"""Собрать Colab-ноутбук «видео → GVHMR → дубль MoCapGate (JSON + BVH)».

    python3 tools/build_colab.py            # → colab/MoCapGate_GVHMR.ipynb

Ноутбук самодостаточный: модули ядра MoCapGate (SMPL-X → BVH) встраиваются в него
при сборке, поэтому он работает и при приватном репозитории, и без установки
MoCapGate. Пересобирать после правок core/*.py (тест tests/test_colab.py это ловит).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "colab" / "MoCapGate_GVHMR.ipynb"
CORE = ("__init__.py", "rotations.py", "skeleton.py", "bvh.py", "smpl.py", "smpl_bvh.py", "gvhmr.py")
GVHMR_COMMIT = "ee960bb6e2ea2d381aa97f08e9b71ef320b624b1"  # проверенный срез zju3dv/GVHMR
HF_WEIGHTS = "https://huggingface.co/camenduru/GVHMR/resolve/main"  # зеркало весов GVHMR (без моделей тела)


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str, title: str | None = None, hidden: bool = False) -> dict:
    meta: dict = {}
    if title:
        meta["cellView"] = "form"
    if hidden:
        meta["jupyter"] = {"source_hidden": True}
    src = (f"#@title {title}\n" if title else "") + text.strip("\n")
    return {"cell_type": "code", "metadata": meta, "execution_count": None, "outputs": [],
            "source": src.splitlines(keepends=True)}


INTRO = """
# MoCapGate × GVHMR — мокап из видео на GPU Colab

**Видео → движение всего тела в мировых координатах (GVHMR, SIGGRAPH Asia 2024) → BVH для Blender / Maya
и файл дубля для MoCapGate Studio.** *Video → GVHMR world-grounded motion → BVH + a MoCapGate take.*

Как пользоваться:
1. **Среда выполнения → Сменить среду → GPU (T4 подойдёт)**.
2. Запустите ячейки по порядку (▶ слева или *Среда выполнения → Выполнить всё*). Первая установка — 6–10 минут,
   дальше в той же сессии — секунды.
3. На шаге 3 загрузите **SMPLX_NEUTRAL.npz** — бесплатная регистрация на
   [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de) → *Download* → *SMPL-X v1.1 (NPZ)*. Один раз положите файл
   в Google Drive в папку `MoCapGate/` — дальше ноутбук найдёт его сам.
4. На шаге 4 загрузите видео (или возьмите пример). Результат — архив с `*.bvh` и `*.mocapgate.json`:
   BVH сразу в Blender (*Import → Motion Capture*, Scale 0.01), JSON — в MoCapGate Studio для проверки и экспорта.

Советы по съёмке: человек целиком в кадре, камера на уровне пояса, хороший свет, без сильного размытия.
Если камера стоит на месте — включите `static_camera`: так точнее.

> Лицензии: GVHMR и модель SMPL-X — **только для некоммерческого использования**. Видео обрабатывается в вашей
> сессии Colab и никуда больше не уходит.
"""

SETTINGS = """
max_people = 4  #@param {type:"integer"}
#@markdown ↑ максимум участников (1–8), отдельный BVH для каждого
static_camera = False  #@param {type:"boolean"}
#@markdown ↑ камера неподвижна (штатив) — точнее и быстрее
focal_mm = 0  #@param {type:"integer"}
#@markdown ↑ фокусное расстояние в мм (35-мм экв.): iPhone 0.5×/1×/2×/3× ≈ 13/24/48/77. 0 — оценить автоматически
target_fps = 30  #@param {type:"integer"}
#@markdown ↑ GVHMR обучен на 30 fps — видео приводится к этой частоте
save_to_drive = True  #@param {type:"boolean"}
#@markdown ↑ сохранить результат в Google Drive → MoCapGate/out
"""

GPU = """
import subprocess
out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
if out.returncode != 0:
    raise SystemExit("Нет GPU. Среда выполнения → Сменить среду выполнения → T4 GPU, затем запустите ячейки заново.")
print("GPU:", out.stdout.strip())
"""

INSTALL = f"""
import os, subprocess, pathlib
GV = pathlib.Path("/content/GVHMR"); VENV = pathlib.Path("/content/gvhmr-venv"); PY = VENV / "bin/python"
def sh(cmd):
    print("$", cmd); subprocess.run(cmd, shell=True, check=True)
if not (GV / ".ok").exists():
    sh("pip -q install uv")
    if not GV.exists():
        sh(f"git clone -q https://github.com/zju3dv/GVHMR {{GV}} && git -C {{GV}} checkout -q {GVHMR_COMMIT}")
    sh(f"uv venv -q -p 3.10 {{VENV}}")
    uv = f"uv pip install -q -p {{PY}}"
    sh(f"{{uv}} torch==2.3.0+cu121 torchvision==0.18.0+cu121 --index-url https://download.pytorch.org/whl/cu121")
    sh(f"{{uv}} numpy==1.23.5 cython setuptools wheel")
    sh(f"{{uv}} timm==0.9.12 lightning==2.3.0 hydra-core==1.3 hydra-zen hydra_colorlog rich matplotlib "
       f"tensorboardX opencv-python ffmpeg-python scikit-image termcolor einops imageio==2.34.1 av==13.0.0 joblib "
       f"trimesh smplx wis3d pycolmap ultralytics==8.2.42 lapx yacs")
    sh(f"{{uv}} --no-build-isolation cython_bbox")
    sh(f"{{uv}} https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu121_pyt230/"
       f"pytorch3d-0.7.6-cp310-cp310-linux_x86_64.whl")
    sh(f"{{uv}} --no-deps -e {{GV}}")
    ck = GV / "inputs/checkpoints"
    for rel in ("gvhmr/gvhmr_siga24_release.ckpt", "hmr2/epoch=10-step=25000.ckpt",
                "vitpose/vitpose-h-multi-coco.pth", "yolo/yolov8x.pt"):
        dst = ck / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            sh(f"curl -sSfL -o '{{dst}}' '{HF_WEIGHTS}/{{rel.replace('=', '%3D')}}'")
    (GV / ".ok").touch()
print("GVHMR готов:", GV)
"""

BODY = """
import shutil, numpy as np
from pathlib import Path
dst = GV / "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz"
dst.parent.mkdir(parents=True, exist_ok=True)
drive_dir = Path("/content/drive/MyDrive/MoCapGate")
if not dst.exists():
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        found = sorted(drive_dir.glob("SMPLX_NEUTRAL*.npz")) if drive_dir.exists() else []
        if found:
            shutil.copy(found[0], dst); print("Взял из Drive:", found[0])
    except Exception as e:
        print("Drive не подключён:", e)
if not dst.exists():
    from google.colab import files
    print("Загрузите SMPLX_NEUTRAL.npz (smpl-x.is.tue.mpg.de → SMPL-X v1.1 NPZ)")
    up = files.upload()
    name = next(iter(up))
    Path(name).replace(dst)
m = np.load(dst, allow_pickle=True)
missing = [k for k in ("v_template", "shapedirs", "J_regressor") if k not in m.files]
if missing:
    dst.unlink(); raise SystemExit(f"Это не модель SMPL-X: нет {missing}. Нужен SMPLX_NEUTRAL.npz")
print("SMPL-X на месте:", dst, m["v_template"].shape)
"""

VIDEO = """
use_example = False  #@param {type:"boolean"}
#@markdown ↑ взять пример GVHMR (теннис) вместо своего видео
from pathlib import Path
import subprocess, json
IN = Path("/content/in"); IN.mkdir(exist_ok=True)
if use_example:
    src = GV / "docs/example_video/tennis.mp4"
else:
    from google.colab import files
    print("Загрузите видео (mp4 / mov / webm)")
    up = files.upload()
    src = IN / next(iter(up))
    Path(next(iter(up))).replace(src)
name = "".join(c if c.isalnum() or c in "-_" else "_" for c in src.stem)[:60] or "take"
video = IN / f"{name}.mp4"
probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
    "stream=width,height,avg_frame_rate,nb_frames", "-of", "json", str(src)], capture_output=True, text=True).stdout)["streams"][0]
num, den = (probe.get("avg_frame_rate") or "30/1").split("/")
src_fps = float(num) / float(den or 1)
print(f"{src.name}: {probe['width']}×{probe['height']}, {src_fps:.2f} fps")
# GVHMR ждёт 30 fps: приводим частоту и кодек (webm/HEVC → H.264)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", f"fps={target_fps}", "-c:v", "libx264",
                "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(video)], check=True)
print("Готово к обработке:", video)
"""

RUN = """
import subprocess, sys
runner = Path("/content/gvhmr_runner.py")
runner.write_text(RUNNER_CODE)
out_dir = Path("/content/out") / name
cmd = [str(PY), str(runner), str(GV), str(video), str(out_dir), "--fps", str(target_fps)]
cmd += ["--max-people", str(max_people)]
cmd += ["--static"] if static_camera else []
cmd += ["--f-mm", str(focal_mm)] if focal_mm else []
p = subprocess.run(cmd, capture_output=True, text=True)
print(p.stdout[-3000:])
if p.returncode != 0:
    print(p.stderr[-6000:]); raise SystemExit("GVHMR завершился с ошибкой — текст выше")
result_json = next(l.split(" ", 1)[1] for l in p.stdout.splitlines() if l.startswith("RESULT "))
print("Результат GVHMR:", result_json)
"""

EXPORT = """
import sys, json, shutil, zipfile
sys.path.insert(0, "/content")
from mocapgate_core import gvhmr as mg_gvhmr, smpl_bvh, bvh as mg_bvh
OUT = Path("/content/out") / name; OUT.mkdir(parents=True, exist_ok=True)
take = json.loads(Path(result_json).read_text())
take["video"] = {"name": src.name, "width": int(probe["width"]), "height": int(probe["height"]), "source_fps": src_fps}
take_path = OUT / f"{name}.mocapgate.json"
take_path.write_text(json.dumps(take))
bvh_paths = []
for person in mg_gvhmr.load_people(str(take_path), "global"):
    params = person["params"]
    skel, frames = smpl_bvh.convert(params, str(GV / "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz"))
    bvh_path = OUT / f"{name}_person_{person['id']}.bvh"
    bvh_path.write_text(mg_bvh.write(skel, frames, 1 / target_fps))
    bvh_paths.append(bvh_path)
shutil.copy(video, OUT / f"{name}.mp4")  # видео 30 fps — для проверки в Studio (оверлей кадр в кадр)
zip_path = Path("/content") / f"{name}_mocapgate.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for f in (take_path, *bvh_paths, OUT / f"{name}.mp4"):
        z.write(f, f.name)
print(f"{len(bvh_paths)} участников, {len(frames)} кадров → BVH + {take_path.name}")
if save_to_drive and Path("/content/drive/MyDrive").exists():
    d = Path("/content/drive/MyDrive/MoCapGate/out"); d.mkdir(parents=True, exist_ok=True)
    shutil.copy(zip_path, d / zip_path.name); print("Сохранено в Drive:", d / zip_path.name)
from google.colab import files
files.download(str(zip_path))
"""

PREVIEW = """
import matplotlib.pyplot as plt
from mocapgate_core import smpl
g = params
idx = [int(i * (len(g["transl"]) - 1) / 4) for i in range(5)]
fig, axes = plt.subplots(1, 5, figsize=(16, 4))
for ax, i in zip(axes, idx):
    P = smpl.fk(g["global_orient"][i], g["body_pose"][i], g["transl"][i])
    for j, par in enumerate(smpl.PARENTS):
        if par >= 0:
            ax.plot([P[par][0], P[j][0]], [P[par][1], P[j][1]], "-", lw=2,
                    color="tab:red" if smpl.NAMES[j].startswith("Left") else "tab:blue" if smpl.NAMES[j].startswith("Right") else "k")
    ax.set_aspect("equal"); ax.set_title(f"кадр {i}"); ax.invert_xaxis()
plt.suptitle("Скелет спереди (красный — левая сторона)"); plt.show()
"""


def RUNNER_CODE() -> str:
    return (ROOT / "core" / "gvhmr_runner.py").read_text(encoding="utf-8")


def build() -> dict:
    cells = [md(INTRO), code(SETTINGS, "Шаг 0. Настройки"), code(GPU, "Шаг 1. Проверка GPU"),
             code(INSTALL, "Шаг 2. Установка GVHMR (один раз за сессию, 6–10 мин)")]
    core_cells = []
    for name in CORE:
        src = (ROOT / "core" / name).read_text(encoding="utf-8").replace("from core", "from mocapgate_core")
        core_cells.append(f"%%writefile /content/mocapgate_core/{name}\n{src}")
    cells.append(code("import os; os.makedirs('/content/mocapgate_core', exist_ok=True)", "Ядро MoCapGate (SMPL-X → BVH)"))
    cells += [code(c, hidden=True) for c in core_cells]
    cells += [
        code(BODY, "Шаг 3. Модель тела SMPL-X (Drive → MoCapGate/ или загрузка)"),
        code(VIDEO, "Шаг 4. Видео"),
        code(f"RUNNER_CODE = {RUNNER_CODE()!r}\n" + RUN, "Шаг 5. GVHMR: поза и траектория"),
        code(EXPORT, "Шаг 6. BVH + дубль MoCapGate → скачать"),
        code(PREVIEW, "Шаг 7. Быстрый просмотр скелета"),
        md("Дальше: перетащите архив (или `.mocapgate.json` вместе с `.mp4`) в **MoCapGate Studio** — там проверка "
           "поверх видео, 3D-просмотр, сглаживание и экспорт в FBX для Maya и движков."),
    ]
    return {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
            "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4", "name": "MoCapGate_GVHMR"},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"},
                         "language_info": {"name": "python"}}}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
