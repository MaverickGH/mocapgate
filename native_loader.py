"""Load a platform-specific library with the bundled CPython. See LICENSE."""
import importlib.util
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load(key):
    machine = {"aarch64": "arm64", "amd64": "x86_64"}.get(platform.machine().lower(), platform.machine().lower())
    catalog = ROOT / "native-manifests" / (sys.platform + "-" + machine + ".json")
    manifest = json.loads((catalog if catalog.is_file() else ROOT / "native-manifest.json").read_text(encoding="utf-8"))
    if (sys.implementation.cache_tag != manifest["abi"] or sys.platform != manifest["system"]
            or machine != manifest["machine"]):
        raise RuntimeError("This native package needs its bundled Python and matching OS/architecture. Run START.sh or START_WINDOWS.cmd.")
    entry = manifest["modules"][key]
    name = entry["module"]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / entry["library"])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]
