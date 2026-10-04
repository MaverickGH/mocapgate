#!/usr/bin/env python3
"""Скачать веб-библиотеки Studio в apps/studio/ui/vendor, чтобы приложение работало офлайн.

    python3 scripts/vendor_web.py

- three.js — 3D-просмотр BVH (three.module.js, OrbitControls, BVHLoader);
- @mediapipe/tasks-vision — живая проверка позы с камеры (JS + wasm).
Сборка приложения запускает это перед упаковкой; без папки vendor сервер отдаёт файлы с CDN.
Только stdlib.
"""
from __future__ import annotations
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "studio" / "ui" / "vendor"
THREE_VERSION = "0.169.0"
TASKS_VERSION = "0.10.21"
FILES = {
    f"three/build/three.module.js": f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/build/three.module.js",
    f"three/examples/jsm/controls/OrbitControls.js":
        f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/examples/jsm/controls/OrbitControls.js",
    f"three/examples/jsm/loaders/BVHLoader.js":
        f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/examples/jsm/loaders/BVHLoader.js",
}
for name in ("vision_bundle.mjs", "wasm/vision_wasm_internal.js", "wasm/vision_wasm_internal.wasm",
             "wasm/vision_wasm_nosimd_internal.js", "wasm/vision_wasm_nosimd_internal.wasm"):
    FILES[f"tasks-vision/{name}"] = f"https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@{TASKS_VERSION}/{name}"


def main() -> int:
    for rel, url in FILES.items():
        dst = OUT / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        dst.write_bytes(data)
        print(f"{rel} ({len(data) / 2 ** 20:.1f} MB)")
    print(f"vendor: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
