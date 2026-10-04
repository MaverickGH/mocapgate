#!/usr/bin/env python3
"""Package a verified target-specific native distribution.

    python3 scripts/make_portable.py --native-package dist/native-package --out dist

Original source packaging is available only with explicit --source for local use.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ["mocapgate.py", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "README.en.md", "requirements.txt", "core", "apps/studio/server.py",
           "apps/studio/ui", "apps/studio/README.md", "colab", "docs", "targets", "tools", "scripts/vendor_web.py",
           "scripts/setup_windows.ps1", "scripts/start_windows.cmd", "scripts/configure_surface.py",
           "scripts/setup_macos.sh", "scripts/start_macos.command", "scripts/install_ffmpeg.py",
           "scripts/install_example.py", "scripts/prepare_models.py", "examples/sports2d", "tests/fixtures/sports2d/two_people.mp4",
           "tests/fixtures/sports2d/expected.json", "tests/fixtures/sports2d/LICENSE", "tests/fixtures/sports2d/README.md"]
SKIP = re.compile(r"(^\._|__pycache__|\.pyc$|\.DS_Store$)")
START = """MoCapGate Studio — переносная версия · portable

Нужен Python 3.9+ (через pip ставить ничего не нужно). В этой папке:

    python3 mocapgate.py doctor     # что найдено и чего не хватает
    python3 mocapgate.py studio     # открывает Studio в браузере (работает только на этом компьютере)

Распознавание позы на компьютере: Studio → «Статус и ИИ» → MediaPipe → Установить (нужен uv).
Лучшее качество — GVHMR в Colab: Studio → «Новый дубль» → GVHMR · Colab.
Дубли сохраняются в ~/Documents/MoCapGate Takes.

Needs Python 3.9+ (nothing to pip install). In this folder: python3 mocapgate.py studio
"""


def version() -> str:
    m = re.search(r'^VERSION = "([^"]+)"', (ROOT / "apps" / "studio" / "server.py").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "dev"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", default=version())
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--keep", help="ещё и оставить распакованную папку здесь (для тестов)")
    ap.add_argument("--source", action="store_true", help="explicit local source package; never publish as a native release")
    ap.add_argument("--native-package", type=Path, help="verified native package for this OS/architecture")
    args = ap.parse_args()
    if not args.source:
        if not args.native_package:
            ap.error("provide --native-package; source distributions require explicit --source")
        from native_packaging import archive, check
        manifest = check(args.native_package.resolve())
        name = f"MoCapGate-{args.version}-{manifest['system']}-{manifest['machine']}-native.zip"
        result = archive(args.native_package.resolve(), Path(args.out).resolve() / name)
        if args.keep:
            dest = Path(args.keep).resolve()
            if dest.exists(): ap.error("--keep destination already exists")
            shutil.copytree(args.native_package, dest)
        print(result)
        return 0
    if not (ROOT / "apps" / "studio" / "ui" / "vendor" / "three" / "build" / "three.module.js").exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "vendor_web.py")])
    name = f"MoCapGate-{args.version}-portable"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / name
        for rel in INCLUDE:
            src = ROOT / rel
            if src.is_dir():
                shutil.copytree(src, stage / rel, ignore=lambda d, names: [n for n in names if SKIP.search(n)])
            elif src.exists():
                (stage / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, stage / rel)
            else:
                print(f"нет файла: {rel}")
                return 1
        (stage / "START.txt").write_text(START, encoding="utf-8")
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        archive = out / f"{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for f in sorted(stage.rglob("*")):
                if f.is_file():
                    info=zipfile.ZipInfo.from_file(f,f.relative_to(stage.parent))
                    if f.suffix in ('.command','.sh'):
                        info.create_system=3
                        info.external_attr=(0o100755<<16)
                    info.compress_type=zipfile.ZIP_DEFLATED
                    contents=f.read_bytes()
                    if f.suffix in ('.command','.sh'):
                        contents=contents.replace(b'\r\n',b'\n')
                    z.writestr(info,contents)
        if args.keep:
            dest = Path(args.keep).resolve()
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(stage, dest)
    print(f"{archive} ({archive.stat().st_size / 2 ** 20:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
