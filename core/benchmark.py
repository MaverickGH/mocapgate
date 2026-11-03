"""MoCapGate — тест производительности GEM-X на этом компьютере.

Короткое демо-видео (два человека) прогоняется через GEM-X с замером: время по этапам, пики видеопамяти
и оперативной памяти (в WSL — память виртуальной машины). По результату — рекомендуемые настройки
(режим модели, обработка частями, число людей). Запускается отдельным процессом, события — JSON-строки:

    python core/benchmark.py
"""
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VIDEOS = (ROOT / "tests/fixtures/sports2d/two_people.mp4", ROOT / "examples/sports2d/input.mp4")


def result_path():
    from core import settings
    return settings.config_dir() / "benchmark.json"


def last():
    path = result_path()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None


def run(quality="fast"):
    from core import pipeline, resources, settings
    from core.gemx import ready, runtime
    from core.gvhmr_environment import linux_path, worker_command, wsl_prefix
    from core.video_timing import normalize
    if not ready():
        raise RuntimeError("Установите GEM-X в разделе «Модели и инструменты».")
    video = next((v for v in VIDEOS if v.is_file()), None)
    if not video:
        raise RuntimeError("В пакете нет демо-видео для теста — переустановите Studio")
    cfg = runtime()
    before = resources.sample(settings.load())
    work = Path(tempfile.mkdtemp(prefix="mocapgate-benchmark-", dir=settings.config_dir()))
    try:
        pipeline.emit("video", "Готовлю демо-видео: 30 FPS, 1920 px…", 0.05, step="Подготовка видео")
        clip = work / "bench.mp4"
        normalize(video, clip, 30, cfg, max_px=1920)
        out = work / "bench.json"
        extra = ["--fps", "30", "--quality", quality, "--max-people", "2", "--benchmark"]
        if cfg.get("gvhmr_wsl"):
            command = wsl_prefix(cfg) + [cfg["gvhmr_python"], linux_path(ROOT / "core/gemx_runner.py", cfg),
                                         cfg["gvhmr_dir"], linux_path(clip, cfg), linux_path(out, cfg), *extra]
        else:
            command = worker_command(cfg, ROOT / "core/gemx_runner.py", cfg["gvhmr_dir"], clip, out, *extra)
        pipeline.emit("gemx", "GEM-X: тест на демо-видео (первый запуск загружает модели)…", 0.1, step="Тест GEM-X")
        started = time.monotonic()
        code, lines = pipeline._run_streaming(command, "gemx")
        if code or not out.is_file():
            raise RuntimeError(pipeline.failure_summary("GEM-X (тест)", code, lines))
        measured = json.loads(out.read_text(encoding="utf-8"))
        totals = resources.sample(settings.load())
        machine = {"vram_total_mb": max((g.get("vram_total_mb") or 0 for g in totals.get("gpu") or []), default=None),
                   "ram_total_mb": totals.get("wsl_ram_total_mb") or totals.get("ram_total_mb")}
        result = {"format": "mocapgate.benchmark/1", "time": time.strftime("%Y-%m-%d %H:%M:%S"), "quality": quality,
                  "wall_seconds": round(time.monotonic() - started, 1), "measured": measured, "machine": totals,
                  "before": before, "recommend": resources.recommend(measured, machine)}
        path = result_path()
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        peaks = measured.get("resources") or {}
        pipeline.emit("done", f"Тест готов: {measured.get('fps_processing', 0):.1f} кадр/с, пик видеопамяти "
                              f"{(peaks.get('vram_mb') or 0) / 1024:.1f} ГБ, ОЗУ {(peaks.get('ram_mb') or 0) / 1024:.1f} ГБ", 1)
        return result
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else "fast")
    except Exception as exc:  # noqa: BLE001 — причина должна дойти до окна
        from core.pipeline import emit
        emit("error", str(exc))
        raise SystemExit(1)
