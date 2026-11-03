#!/usr/bin/env python3
"""Install the pinned upstream Linux GVHMR runtime; never redistribute body models."""
import json
import hashlib
import urllib.request
import urllib.parse
import os
from pathlib import Path
import platform
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.install_util import fetch, ensure_venv, clone  # noqa: E402

REVISION = 'ee960bb6e2ea2d381aa97f08e9b71ef320b624b1'
WEIGHTS = 'https://drive.google.com/drive/folders/1eebJ13FUEXrKBawHpJroW0sNSxLjh9xD'
REQUIRED = ['gvhmr/gvhmr_siga24_release.ckpt', 'hmr2/epoch=10-step=25000.ckpt',
            'vitpose/vitpose-h-multi-coco.pth', 'yolo/yolov8x.pt']

MIRROR_REVISION = '21b32d5389e2e59c0737d4c4095bbc0b8c23f66b'
WEIGHT_FILES = {'gvhmr/gvhmr_siga24_release.ckpt': {'size': 163508011, 'sha256': '4fae7da2de388d5da3514cb27a2d003f364dacb280e9cf88972b710e589c6b91'}, 'hmr2/epoch=10-step=25000.ckpt': {'size': 2709494041, 'sha256': '2dcf79638109781d1ae5f5c44fee5f55bc83291c210653feead9b7f04fa6f20e'}, 'vitpose/vitpose-h-multi-coco.pth': {'size': 2549075546, 'sha256': '50e33f4077ef2a6bcfd7110c58742b24c5859b7798fb0eedd6d2215e0a8980bc'}, 'yolo/yolov8x.pt': {'size': 136867539, 'sha256': 'c4d5a3f000d771762f03fc8b57ebd0aae324aeaefdd6e68492a9c4470f2d1e8b'}}

def run(*args):
    subprocess.run(list(map(str, args)), check=True)


def verified_weight(path, relative):
    expected = WEIGHT_FILES[relative]
    if not path.is_file() or path.stat().st_size != expected['size']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == expected['sha256']


def mirror_weight(relative, temporary):
    """Докачка (Range) с повторами в <temporary>.part; размер проверяется до переименования."""
    url = 'https://huggingface.co/camenduru/GVHMR/resolve/' + MIRROR_REVISION + '/' + urllib.parse.quote(relative, safe='/')
    expected = WEIGHT_FILES[relative]
    # SHA-256 проверяет download_weights: второй проход по 2.7 ГБ не нужен.
    fetch(url, temporary, size=expected['size'], log=lambda m: print(m, flush=True), timeout=120, label=relative)


def download_weights(destination, download=True):
    import gdown
    if not download:
        for relative in REQUIRED:
            print(relative, flush=True)
        return
    missing = [relative for relative in REQUIRED if not verified_weight(destination/relative, relative)]
    if not missing:
        return
    try:
        entries = gdown.download_folder(url=WEIGHTS, skip_download=True, quiet=True) or []
    except Exception as exc:
        print('Google Drive: ' + str(exc), flush=True)
        entries = []
    for relative in missing:
        dst = destination/relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        temporary = dst.with_name(dst.name + '.download')
        candidates = [item for item in entries if Path(item.path).name == dst.name]
        try:
            if len(candidates) != 1:
                raise RuntimeError('Google Drive не вернул файл: ' + relative)
            result = gdown.download(id=candidates[0].id, output=str(temporary), resume=True)
            if result is None or not verified_weight(temporary, relative):
                raise RuntimeError('Google Drive: скачивание ограничено или файл не прошёл SHA-256: ' + relative)
        except Exception as exc:
            print(str(exc) + '\nИспользую резервное зеркало camenduru/GVHMR (проверка размера и SHA-256).', flush=True)
            mirror_weight(relative, temporary)
        if not verified_weight(temporary, relative):
            temporary.unlink(missing_ok=True)
            raise RuntimeError('Веса не прошли проверку размера / SHA-256: ' + relative)
        temporary.replace(dst)
        print('Веса проверены: ' + relative, flush=True)


def main():
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise RuntimeError('Окружение GVHMR требует Linux x64 (на Windows — WSL2).')
    home = Path.home()/'.cache/mocapgate/gvhmr'
    home.mkdir(parents=True, exist_ok=True)
    repo, env = home/'repo', home/'venv'
    # Bootstrap uv in an isolated host venv; the managed GPU runtime remains Python 3.10.
    tools = home/'tools'
    ensure_venv(tools, lambda: run(sys.executable, '-m', 'venv', tools))
    run(tools/'bin/python', '-m', 'pip', 'install', 'uv==0.12.19')
    uv = tools/'bin/uv'
    clone('https://github.com/zju3dv/GVHMR.git', repo, run)
    run('git', '-C', repo, 'checkout', '--detach', REVISION)
    py = ensure_venv(env, lambda: run(uv, 'venv', '--python', '3.10', '--seed', env))
    os.environ['PYTHONUTF8'] = '1'
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '1')
    # Only skip installation after the same revision has completed successfully.
    marker = home/'installed.json'
    installed = json.loads(marker.read_text()) if marker.exists() else {}
    if installed.get('revision') != REVISION:
        # chumpy's legacy setup imports pip without declaring it as a build dependency.
        run(uv, 'pip', 'install', '--python', py, 'setuptools==69.5.1', 'wheel', 'numpy==1.23.5')
        run(uv, 'pip', 'install', '--python', py, '--no-build-isolation-package', 'chumpy', '-r', repo/'requirements.txt')
        run(uv, 'pip', 'install', '--python', py, '-e', repo, 'gdown==5.2.0')
    imports = "import sys; sys.path[:0]="+repr([str(repo),str(repo/'tools/demo')])+"; import torch,pytorch3d,hydra,smplx,cv2,pycolmap,cython_bbox; from pytorch3d import _C; import demo; print('GVHMR imports OK')"
    run(py, '-c', imports)
    if '--verify-dependencies' in sys.argv:
        return
    run(py, '-c', "import torch,pytorch3d,hydra,smplx; "
        "assert torch.cuda.is_available(), 'PyTorch не видит NVIDIA CUDA'; "
        "x=torch.ones(1,device='cuda'); print('GPU:',torch.cuda.get_device_name(0),flush=True)")
    destination = repo/'inputs/checkpoints'
    destination.mkdir(parents=True, exist_ok=True)
    if not all(verified_weight(destination/p, p) for p in REQUIRED):
        print('Скачиваю официальные веса GVHMR. Это может занять несколько минут…', flush=True)
        run(py, __file__, '--download-weights', destination)
    runtime = {'revision':REVISION,'dir':str(repo),'python':str(py)}
    marker.write_text(json.dumps(runtime))
    print('MOCAPGATE_RUNTIME '+json.dumps(runtime), flush=True)


if __name__ == '__main__':
    if '--download-weights' in sys.argv:
        download_weights(Path(sys.argv[-1]))
    elif '--list-weights' in sys.argv:
        download_weights(Path('.'), download=False)
    else:
        main()
