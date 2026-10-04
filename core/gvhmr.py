"""MoCapGate — адаптер GVHMR (https://github.com/zju3dv/GVHMR, некоммерческая лицензия).

GVHMR запускается отдельно (нужен CUDA-GPU: Colab, HF Space, облако):
    python tools/demo/demo.py --video клип.mp4 [-s]
и кладёт результат в outputs/demo/<клип>/hmr4d_results.pt. Там словарь:
    smpl_params_global / smpl_params_incam: body_pose (L,63), betas (L,10),
                                            global_orient (L,3), transl (L,3)
    K_fullimg (L,3,3)
Глобальная система GVHMR — Y вверх (по гравитации), как в BVH.

Читаем три формата:
    .pt   — оригинал, нужен torch (CPU-версии достаточно);
    .npz  — нужен numpy;
    .json — только stdlib: формат «дубль MoCapGate» (colab/MoCapGate_GVHMR.ipynb,
            tools/gvhmr_export.py) — те же ключи плюс fps исходника и сведения о видео.
"""
from __future__ import annotations
import json
from pathlib import Path

KEYS = ("global_orient", "body_pose", "transl", "betas")
SPACES = ("global", "incam")


def _tolist(x):
    return x.tolist() if hasattr(x, "tolist") else x


def _pick(data: dict, space: str) -> dict:
    """Вытащить параметры нужного пространства из любой из раскладок."""
    nested = data.get(f"smpl_params_{space}")
    if isinstance(nested, dict):
        src = nested
    else:  # плоская раскладка: "smpl_params_global.body_pose" или просто "body_pose"
        pref = f"smpl_params_{space}."
        src = {k[len(pref):]: v for k, v in data.items() if k.startswith(pref)} or data
    missing = [k for k in KEYS[:3] if k not in src]
    if missing:
        raise KeyError(f"в результатах GVHMR нет {missing} (пространство '{space}'); ключи: {sorted(data)}")
    out = {k: _tolist(src[k]) for k in KEYS if k in src}
    # torch/numpy могут отдать лишнюю batch-ось (1, L, C)
    for k in KEYS[:3]:
        if out[k] and isinstance(out[k][0], list) and out[k][0] and isinstance(out[k][0][0], list):
            out[k] = out[k][0]
    return out


def _read(path: str) -> dict:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
    elif ext == ".npz":
        import numpy as np  # type: ignore
        z = np.load(p, allow_pickle=True)
        data = {k: (z[k].item() if z[k].dtype == object and z[k].shape == () else z[k]) for k in z.files}
    elif ext == ".pt":
        try:
            import torch  # type: ignore
        except ImportError:
            raise RuntimeError(
                "для .pt нужен torch (pip install torch) — или конвертируй в JSON рядом с GVHMR: "
                "python tools/gvhmr_export.py hmr4d_results.pt"
            ) from None
        data = torch.load(p, map_location="cpu", weights_only=False)
    else:
        raise ValueError(f"неизвестный формат результатов GVHMR: {ext} (ожидаю .pt/.npz/.json)")
    return data


def from_data(data: dict, space: str = "global") -> dict:
    if space not in SPACES:
        raise ValueError(f"space должен быть одним из {SPACES}")
    params = _pick(data, space)
    params["cam_to_yup"] = space == "incam"  # камерная система OpenCV: Y вниз — перевернём в конвертере
    # для оверлея-проверки поверх видео нужны параметры в системе камеры и интринсики
    if space == "global" and isinstance(data.get("smpl_params_incam"), dict):
        params["incam"] = _pick(data, "incam")
    K = data.get("K_fullimg")
    if K is not None:
        K = _tolist(K)
        params["K"] = K[0] if K and isinstance(K[0][0], list) else K  # (L,3,3) → первого кадра
    if data.get("fps"):
        params["fps"] = float(_tolist(data["fps"]))
    if isinstance(data.get("video"), dict):
        params["video"] = data["video"]
    return params


def load_people(path: str, space: str = "global") -> list[dict]:
    data = _read(path)
    if "people" not in data:
        return [{"id": 1, "params": from_data(data, space)}]
    if not isinstance(data["people"], list) or not data["people"]:
        raise ValueError("в результатах нет участников")
    result, seen = [], set()
    for index, person in enumerate(data["people"], 1):
        pid = person.get("id", index)
        if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1 or pid in seen:
            raise ValueError("ID участников должны быть уникальными положительными числами")
        seen.add(pid)
        params = from_data({**{k: data[k] for k in ("fps", "video") if k in data}, **person}, space)
        result.append({"id": pid, "params": params,
                       **{k: person[k] for k in ("start_frame", "end_frame") if k in person}})
    counts = {len(p["params"]["transl"]) for p in result}
    if len(counts) != 1 or not next(iter(counts)):
        raise ValueError("участники должны иметь одинаковую длину общего таймлайна")
    if len({p["params"].get("fps", 30) for p in result}) != 1:
        raise ValueError("участники должны иметь одинаковую частоту кадров")
    return result


def load(path: str, space: str = "global") -> dict:
    """Legacy single-person API; scenes use load_people to preserve every track."""
    return load_people(path, space)[0]["params"]
