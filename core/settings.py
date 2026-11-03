"""MoCapGate — настройки пользователя (JSON в папке конфигурации ОС).

macOS   ~/Library/Application Support/MoCapGate/settings.json
Windows %APPDATA%\\MoCapGate\\settings.json
Linux   $XDG_CONFIG_HOME/mocapgate/settings.json (обычно ~/.config/mocapgate)
MOCAPGATE_HOME переопределяет папку (тесты, переносная версия).
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

DEFAULTS: dict = {
    "capture_hands": False,    # отдельный трекер кистей и 30 костей пальцев
    "capture_face": False,     # 478 точек лица и 52 коэффициента мимики
    "body_surface": False,     # локальная поверхность SMPL-X с точными костями
    "mixamo_namespace": False, # добавить mixamorig: к именам экспортированных костей
    "max_people": 4,            # maximum simultaneous people (1…8)
    "lang": "",                 # "" — по языку системы/браузера; "ru" | "en"
    "check_updates": True,      # раз в 6 ч спрашивать GitHub о новой версии (без данных о пользователе)
    "library": "",              # "" — ~/Documents/MoCapGate Takes
    "backend": "gvhmr-colab",   # legacy MediaPipe remains readable for old takes
    "hand_stability": True,
    "gemx_quality": "fast",     # быстро (ONNX) / точно / максимум — значения по умолчанию для новых дублей GEM-X
    "gemx_chunk_seconds": -1,   # −1 — части по свободной памяти, 0 — целиком, N — по N с
    "gemx_fps": 30,             # 30 — частота распознавания по умолчанию; 0 — как у видео (до 60)
    "recognition_max_px": 1920, # длинная сторона видео для распознавания; 0 — исходный размер
    "gvhmr_hands": "auto",      # кисти дублей GVHMR: auto (GEM-X, если установлен) | gemx | mediapipe
    "smooth_body": 0.0,         # сглаживание дрожания тела 0…1 (One-Euro), 0 — как распознано
    "smooth_hands": 0.45,       # консервативное двустороннее сглаживание вращений пальцев
    "pose_model": "heavy",      # lite | full | heavy (MediaPipe)
    "smoothing": 0.5,           # 0…1
    "root": "image",            # image — траектория из кадра; inplace — на месте
    "foot_lock": True,          # фиксация стоп (не скользят по полу)
    "focal_mm": 0.0,            # фокус камеры, мм 35-мм экв.; 0 — подобрать автоматически
    "space": "global",          # GVHMR: global | incam
    "model_python": "",         # managed CPU runtime for SMPL-X on any supported desktop
    "smplx_model": "",          # путь к SMPLX_NEUTRAL.npz (точные кости)
    "gvhmr_dir": "",            # GVHMR на этом компьютере (нужен NVIDIA GPU)
    "gvhmr_wsl": "",            # managed WSL distribution; empty for native Linux
    "gvhmr_python": "",         # python окружения GVHMR
    "blender": "",              # путь к Blender, если не нашёлся сам
    "maya": "",
    "rig_profile": "",
    "maya_rig": "builtin",      # builtin Man_Rig, empty: capture skeleton, or custom .ma
    "gemx_dir": "",
    "gemx_python": "",
    "gemx_wsl": "",
    "camera_id": "",            # последняя выбранная камера
    "camera_fps": 30,
    "camera_res": "1280x720",
    "countdown": 3,
}


def config_dir() -> Path:
    env = os.environ.get("MOCAPGATE_HOME")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MoCapGate"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "MoCapGate"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "mocapgate"


def path() -> Path:
    return config_dir() / "settings.json"


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        saved = json.loads(path().read_text(encoding="utf-8"))
        data.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def save(changes: dict) -> dict:
    """Сохранить только известные ключи с проверкой типов; вернуть новые настройки."""
    data = load()
    for k, v in changes.items():
        if k not in DEFAULTS:
            raise ValueError(f"неизвестная настройка: {k}")
        want = type(DEFAULTS[k])
        if want is float and isinstance(v, int) and not isinstance(v, bool):
            v = float(v)
        if not isinstance(v, want) or isinstance(v, bool) != isinstance(DEFAULTS[k], bool):
            raise ValueError(f"{k}: ожидается {want.__name__}")
        data[k] = v
    if data["lang"] not in ("", "ru", "en"):
        raise ValueError("lang: ru или en")
    if data["backend"] not in ("mediapipe", "gvhmr-colab", "gvhmr-local", "gemx-local"):
        raise ValueError("backend: mediapipe | gvhmr-colab | gvhmr-local | gemx-local")
    if data["pose_model"] not in ("lite", "full", "heavy"):
        raise ValueError("pose_model: lite | full | heavy")
    if data["root"] not in ("image", "inplace"):
        raise ValueError("root: image | inplace")
    if data["gvhmr_hands"] not in ("auto", "gemx", "mediapipe"):
        raise ValueError("gvhmr_hands: auto | gemx | mediapipe")
    if data["space"] not in ("global", "incam"):
        raise ValueError("space: global | incam")
    if not 1 <= data["max_people"] <= 8:
        raise ValueError("max_people: 1…8")
    data["smoothing"] = min(1.0, max(0.0, data["smoothing"]))
    path().parent.mkdir(parents=True, exist_ok=True)
    tmp = path().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path())
    return data


def library(data: dict | None = None) -> Path:
    data = data or load()
    env = os.environ.get("MOCAPGATE_LIBRARY")
    if env:
        return Path(env).expanduser()
    if data.get("library"):
        return Path(data["library"]).expanduser()
    # не «MoCapGate»: на нечувствительных к регистру дисках это та же папка, что клон репозитория mocapgate
    return Path.home() / "Documents" / "MoCapGate Takes"
