#!/usr/bin/env python3
"""Упакованная копия MoCapGate (из установщика или переносного zip) работает сама по себе.

    python3 tests/test_bundle.py <папка с mocapgate.py>

Проверяет: файлы на месте, офлайн-библиотеки (three.js, MediaPipe Tasks) лежат внутри, сервер
стартует из этой папки, печатает адрес, отдаёт страницу и статус по токену, BVH из GVHMR-дубля
конвертируется без зависимостей.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

NEED = ["mocapgate.py", "LICENSE", "core/pipeline.py", "core/pose_worker.py", "core/person_tracking.py", "core/person_detector.py", "core/blender_io.py", "core/gvhmr_runner.py",
        "apps/studio/server.py", "apps/studio/ui/index.html", "apps/studio/ui/studio.js", "apps/studio/ui/viewer3d.js",
        "apps/studio/ui/vendor/three/build/three.module.js", "apps/studio/ui/vendor/three/examples/jsm/loaders/BVHLoader.js",
        "apps/studio/ui/vendor/tasks-vision/vision_bundle.mjs", "apps/studio/ui/vendor/tasks-vision/wasm/vision_wasm_internal.wasm",
        "colab/MoCapGate_GVHMR.ipynb"]


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    fails = [f"нет файла {rel}" for rel in NEED if not (root / rel).is_file()]
    caches = [str(p) for p in root.rglob("__pycache__")]
    if caches:
        fails.append(f"в пакете кэши Python: {caches[:3]}")
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, MOCAPGATE_HOME=str(Path(tmp) / "cfg"), MOCAPGATE_LIBRARY=str(Path(tmp) / "lib"),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen([sys.executable, str(root / "mocapgate.py"), "studio", "--port", "0", "--no-browser",
                                 "--token", "bundle-test"], cwd=tmp, env=env, stdout=subprocess.PIPE, text=True)
        try:
            url = None
            deadline = time.time() + 30
            while time.time() < deadline and not url:
                line = proc.stdout.readline()
                if line.startswith("MOCAPGATE_STUDIO "):
                    url = line.split(" ", 1)[1].strip()
            if not url:
                fails.append("сервер не напечатал адрес")
            else:
                base = url.split("/?")[0]
                page = urllib.request.urlopen(base + "/", timeout=10).read().decode()
                if "MoCapGate Studio" not in page:
                    fails.append("страница не та")
                st = json.loads(urllib.request.urlopen(base + "/api/status?t=bundle-test", timeout=30).read())
                if not st.get("version"):
                    fails.append("статус без версии")
                three = urllib.request.urlopen(base + "/three/build/three.module.js", timeout=10)
                if three.status != 200:
                    fails.append("three.js не отдаётся локально")
        except Exception as e:  # noqa: BLE001
            fails.append(f"сервер: {e}")
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
        # конвертация GVHMR-дубля без зависимостей
        take = Path(tmp) / "t.mocapgate.json"
        take.write_text(json.dumps({"smpl_params_global": {"global_orient": [[0, 0, 0]] * 3, "body_pose": [[0.0] * 63] * 3,
                                                           "transl": [[0, 0.9, 0]] * 3}}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(root / "mocapgate.py"), str(take), "-o", str(Path(tmp) / "t.bvh")],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0 or not (Path(tmp) / "t.bvh").is_file():
            fails.append("CLI не сделал BVH: " + r.stdout + r.stderr)
        single = json.loads(take.read_text())
        take.write_text(json.dumps({"people": [{"id": 2, **single}, {"id": 5, **single}]}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(root / "mocapgate.py"), str(take), "-o", str(Path(tmp) / "scene.bvh")],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0 or not all((Path(tmp) / f"scene_person_{pid}.bvh").is_file() for pid in (2, 5)):
            fails.append("CLI не сохранил всех участников: " + r.stdout + r.stderr)
    for f in fails:
        print(f"  ✗ {f}")
    print("Результат: " + ("упакованная копия работает." if not fails else f"{len(fails)} проблем."))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
