"""Install pinned GEM-X in an isolated Python 3.12 environment."""
import hashlib
import json
import os
import platform
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.install_util import fetch, ensure_venv, clone  # noqa: E402

REVISION = '32992550dba114c62243fb55e361311972dce8f9'
ORT_CUDA12 = '1.20.2'
# gem/utils/yolox_detector.py на REVISION: тот же URL и тот же кэш, что у _download_yolox_onnx.
YOLOX_URL = ('https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/'
             'onnx_sdk/yolox_x_8xb8-300e_humanart-a39d44ed.zip')
# SOMA depends on unpinned warp-lang. From 1.18.0 the PyPI wheels use CUDA Toolkit 13.4 and
# need an R580+ driver (CUDA 13); with an older driver Warp falls back to CPU ("insufficient
# CUDA driver version"). 1.18.0 is also published as +cu12 builds on GitHub Releases (minor
# version compatibility: any CUDA 12.x driver). Same version → same API for SOMA.
WARP_VERSION = '1.18.0'
WARP_CU12 = {  # arch: (wheel, size, sha256) — GitHub release v1.18.0 asset digests
    'x86_64': ('warp_lang-1.18.0+cu12-py3-none-manylinux_2_28_x86_64.whl', 164625100,
               '6dda3c163dde4edaa7d46ade9fff3ddb1126ee7b147d9d890cd38cc70dafd656'),
    'aarch64': ('warp_lang-1.18.0+cu12-py3-none-manylinux_2_34_aarch64.whl', 172957976,
                '52e05aaafcad71bfbdfbed8b3dc732afe1dd116e3922b63fc24ffb9bd87c020b'),
}


def say(message):
    print(message, flush=True)


def yolox_onnx():
    """Скачать YOLOX (~370 МБ) с докачкой и прогрессом и распаковать атомарно.
    Upstream пишет zip без временного файла и пропускает уже существующий — обрыв ломал все повторы."""
    cache = Path(os.getenv('TORCH_HOME', os.path.expanduser('~/.cache/rtmlib')))/'hub'/'checkpoints'
    name = YOLOX_URL.rsplit('/', 1)[1]
    archive, onnx = cache/name, cache/(name.rsplit('.', 1)[0]+'.onnx')
    if onnx.is_file() and onnx.stat().st_size > 1024**2:
        return onnx
    onnx.unlink(missing_ok=True)
    def usable(path):
        try:
            with zipfile.ZipFile(path) as zipped:
                return zipped.testzip() is None and any(n.endswith('end2end.onnx') for n in zipped.namelist())
        except (OSError, zipfile.BadZipFile):
            return False
    def check(path):
        if not usable(path):
            raise ValueError('YOLOX: архив повреждён — повторите установку')
    if archive.exists() and not usable(archive):
        archive.unlink()
    if not archive.exists():
        fetch(YOLOX_URL, archive, log=say, check=check, timeout=120, label='YOLOX')
    with zipfile.ZipFile(archive) as zipped:
        member = next(n for n in zipped.namelist() if n.endswith('end2end.onnx'))
        part = onnx.with_name(onnx.name+'.part')
        with zipped.open(member) as source, part.open('wb') as output:
            shutil.copyfileobj(source, output, 1024*1024)
    part.replace(onnx)
    archive.unlink(missing_ok=True)
    return onnx


def cuda_runtime_wheel(home):
    """Fetch the CUDA-12 wheel with bounded, resumable, verified transfers."""
    with urllib.request.urlopen(f'https://pypi.org/pypi/onnxruntime-gpu/{ORT_CUDA12}/json', timeout=30) as response:
        metadata = json.load(response)
    arch = platform.machine()
    wheel = next((item for item in metadata['urls']
                  if 'cp312-cp312' in item['filename'] and 'manylinux' in item['filename']
                  and arch in item['filename']), None)
    if wheel is None:
        raise RuntimeError(f'No tested CUDA-12 ONNX Runtime wheel for {arch}/Python 3.12.')
    folder = home/'wheel-downloads'
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder/wheel['filename']
    def verified(path):
        if not path.is_file() or path.stat().st_size != wheel['size']:
            return False
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda: source.read(1024*1024), b''):
                digest.update(block)
        return digest.hexdigest() == wheel['digests']['sha256']
    if verified(dst):
        return dst
    tmp = dst.with_suffix('.part')
    if tmp.exists() and tmp.stat().st_size > wheel['size']:
        raise RuntimeError(f'Invalid partial wheel size: {tmp}')
    offset = tmp.stat().st_size if tmp.exists() else 0
    while offset < wheel['size']:
        end = min(offset+4*1024*1024, wheel['size'])-1
        request = urllib.request.Request(wheel['url'], headers={'Range': f'bytes={offset}-{end}'})
        with urllib.request.urlopen(request, timeout=30) as response:
            expected = f'bytes {offset}-{end}/{wheel["size"]}'
            if response.status != 206 or response.headers.get('Content-Range') != expected:
                raise RuntimeError('Unexpected PyPI wheel range response; refusing to append unverified data.')
            block = response.read()
        if len(block) != end-offset+1:
            raise RuntimeError('Incomplete wheel range; retry setup to resume.')
        with tmp.open('ab') as output:
            output.write(block)
        offset += len(block)
        print(f'ONNX Runtime CUDA 12: {offset // 1024**2}/{wheel["size"] // 1024**2} MiB', flush=True)
    if not verified(tmp):
        raise RuntimeError('ONNX Runtime wheel checksum mismatch.')
    tmp.replace(dst)
    return dst


def warp_requirement(home):
    """Warp for the NVIDIA driver: PyPI build with a CUDA 13 driver, verified +cu12 wheel otherwise."""
    from core.resources import driver_cuda_version
    cuda = driver_cuda_version()
    if cuda and cuda >= (13, 0):
        say(f'NVIDIA driver supports CUDA {cuda[0]}.{cuda[1]}: Warp {WARP_VERSION} (CUDA 13 build).')
        return f'warp-lang=={WARP_VERSION}'
    wheel = WARP_CU12.get(platform.machine())
    if wheel is None:
        return None
    if cuda:
        say(f'NVIDIA driver supports only CUDA {cuda[0]}.{cuda[1]}; Warp {WARP_VERSION} from PyPI needs CUDA 13 '
            '(driver R580 or newer) and would run on CPU. Installing the CUDA 12 build of Warp. '
            'Recommended: update the NVIDIA driver (Windows: 580 or newer) — '
            f'драйвер NVIDIA поддерживает CUDA {cuda[0]}.{cuda[1]}; ставлю Warp для CUDA 12, рекомендуем обновить драйвер до 580+.')
    else:
        say('NVIDIA driver CUDA version unknown: installing the CUDA 12 build of Warp (works with CUDA 12 and 13 drivers).')
    name, size, digest = wheel
    dst = home/'wheel-downloads'/name
    fetch(f'https://github.com/NVIDIA/warp/releases/download/v{WARP_VERSION}/{name.replace("+", "%2B")}',
          dst, digest, size, log=say, timeout=120, label='Warp CUDA 12')
    return dst


def cuda_launcher(env, py):
    """Set pip-provided CUDA library paths before the worker process starts."""
    helper = env/'bin/mocapgate_cuda_env.py'
    helper.write_text('''import os, sys, sysconfig
from pathlib import Path
root = Path(sysconfig.get_path('purelib'))
paths = [root/'torch/lib', *sorted((root/'nvidia').glob('*/lib'))]
environment = dict(os.environ)
existing = environment.get('LD_LIBRARY_PATH', '')
environment['LD_LIBRARY_PATH'] = ':'.join(str(p) for p in paths if p.is_dir()) + (':' + existing if existing else '')
os.execve(sys.executable, [sys.executable, *sys.argv[1:]], environment)
''', encoding='utf-8')
    launcher = env/'bin/mocapgate-python'
    launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(py))+' '+shlex.quote(str(helper))+' "$@"\n', encoding='utf-8')
    launcher.chmod(0o755)
    return launcher


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def git_works():
    try:
        if sys.platform=='darwin' and subprocess.run(['xcode-select','-p'],capture_output=True,timeout=30).returncode:
            return False
        return subprocess.run(['git','--version'],capture_output=True,timeout=60).returncode==0
    except (OSError,subprocess.SubprocessError):
        return False


def main():
    if sys.platform not in ('darwin', 'linux'):
        raise RuntimeError('Windows: install GEM-X in WSL2 using Studio.')
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS','1')
    if sys.platform=='linux' and any(not shutil.which(tool) for tool in ('git','ffmpeg','gcc')):
        apt=shutil.which('apt-get');elevate=[] if os.geteuid()==0 else [shutil.which('pkexec')]
        if not apt or (elevate and not elevate[0]):
            raise RuntimeError('Install git, ffmpeg, python3-venv, python3-dev, build-essential, libgl1 and libglib2.0-0 with your Linux package manager.')
        lock=['-o','DPkg::Lock::Timeout=600','-o','Acquire::Retries=3']
        run(*elevate,apt,*lock,'update')
        run(*elevate,apt,*lock,'install','-y','git','ffmpeg','python3-venv','python3-dev','build-essential','libgl1','libegl1','libglib2.0-0')
    if not shutil.which('git') or not git_works():
        if sys.platform=='darwin':
            raise RuntimeError('Git недоступен — установите Command Line Tools: xcode-select --install, затем повторите установку GEM-X.')
        raise RuntimeError('Git is required. Install Git, then retry GEM-X setup.')
    home = Path(os.environ.get('MOCAPGATE_COMPONENTS_HOME', Path.home()/'.cache/mocapgate'))/'gemx'
    repo, env = home/'repo', home/'venv'
    home.mkdir(parents=True, exist_ok=True)
    required_gb = 30 if sys.platform == 'linux' else 14
    if not repo.exists() and shutil.disk_usage(home).free < required_gb*1024**3:
        raise RuntimeError(f'GEM-X needs at least {required_gb} GB of free disk space for its environment, models and download cache.')
    uv = shutil.which('uv')
    if not uv:
        bootstrap = home/'bootstrap'
        ensure_venv(bootstrap, lambda: run(sys.executable, '-m', 'venv', bootstrap), say)
        run(bootstrap/'bin/python','-m','pip','install','uv==0.12.19')
        uv = bootstrap/'bin/uv'
    clone('https://github.com/NVlabs/GEM-X.git',repo,run)
    run('git','-C',repo,'checkout','--detach',REVISION)
    # Robot retargeter is optional and uses SSH; only initialise public dependencies.
    run('git','-C',repo,'submodule','update','--init','third_party/soma','third_party/sam-3d-body',env={**os.environ,'GIT_LFS_SKIP_SMUDGE':'1'})
    py = ensure_venv(env, lambda: run(uv,'venv','--python','3.12','--seed',env), say)
    args=[uv,'pip','install','--python',py,'torch==2.10.0','torchvision==0.25.0']
    if sys.platform=='linux':
        args[5:7] = ['torch==2.10.0+cu126', 'torchvision==0.25.0+cu126']
        args+=['--default-index','https://download.pytorch.org/whl/cu126',
               '--index','https://pypi.org/simple','--index-strategy','unsafe-best-match']
    run(*args)
    ort = cuda_runtime_wheel(home) if sys.platform=='linux' else 'onnxruntime'
    warp = warp_requirement(home) if sys.platform=='linux' else None
    run(uv,'pip','install','--python',py,'-e',repo/'third_party/soma','-e',repo,
        'numpy==1.26.4','transformers==4.48.3','tokenizers>=0.21',
        'cloudpickle','fvcore','iopath','pycocotools','braceexpand','roma','gdown','cython','lapx','av',  # av — чтение кадров по одному
        ort,*([warp] if warp else []),
        *(['--reinstall-package','warp-lang'] if isinstance(warp, Path) else []))
    # LFS pointer hashes in the pinned submodule verify every required asset.
    # Download directly: users need no separate Git LFS installation.
    soma=repo/'third_party/soma'
    revision=subprocess.check_output(['git','-C',str(soma),'rev-parse','HEAD'],text=True).strip()
    paths=subprocess.check_output(['git','-C',str(soma),'ls-tree','-r','--name-only','HEAD','assets'],text=True).splitlines()
    for name in paths:
        if name not in ('assets/SOMA_neutral.npz','assets/correctives_model.pt') and not name.startswith('assets/MHR/'):
            continue
        pointer=subprocess.check_output(['git','-C',str(soma),'show','HEAD:'+name],text=True)
        if not pointer.startswith('version https://git-lfs.github.com/spec/v1'):continue
        sha=next((line.split(':',1)[1] for line in pointer.splitlines() if line.startswith('oid sha256:')),None)
        size=next((int(line.split()[1]) for line in pointer.splitlines() if line.startswith('size ')),None)
        if not sha or not size:raise RuntimeError('SOMA: неверный LFS-указатель '+name)
        dst=soma/name
        def verified(path):
            if not path.is_file() or path.stat().st_size!=size:return False
            digest=hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
            return digest.hexdigest()==sha
        if verified(dst):continue
        print('Downloading verified SOMA asset: '+name,flush=True)
        fetch('https://media.githubusercontent.com/media/NVlabs/SOMA-X/'+revision+'/'+name,dst,sha,size,log=say,timeout=120)
    assets=repo/'inputs/soma_assets'
    assets.parent.mkdir(exist_ok=True)
    if not assets.exists(): assets.symlink_to(repo/'third_party/soma/assets',target_is_directory=True)
    yolox_onnx()
    run(py,'-c',"from gem.utils.hf_utils import download_onnx_model, download_sam3d_checkpoint, download_mhr_model, download_soma_data, download_checkpoint; [download_onnx_model(n) for n in ('vitpose','gem_denoiser','sam3db_backbone')]; download_sam3d_checkpoint(); download_mhr_model(); download_soma_data(); download_checkpoint(); from gem.utils.yolox_detector import _download_yolox_onnx; _download_yolox_onnx()",cwd=repo)
    worker_py = cuda_launcher(env, py) if sys.platform=='linux' else py
    run(worker_py,'-c','import torch,onnxruntime,soma,hydra,cv2; print("GEM-X imports OK")',cwd=repo)
    if sys.platform=='linux':
        # informative only: SOMA still works with Warp on CPU, just slower
        subprocess.run([str(worker_py),'-c','import warp; warp.init(); print("Warp CUDA:", warp.is_cuda_available())'],
                       cwd=repo, check=False, timeout=300)
    if sys.platform=='linux':
        run(worker_py, '-c', '''import json
from pathlib import Path
import numpy as np
import torch
import onnxruntime as ort
from gem.utils.yolox_detector import _download_yolox_onnx
if not torch.cuda.is_available():
    raise RuntimeError('GEM-X Linux requires an available NVIDIA CUDA GPU.')
options = ort.SessionOptions()
options.enable_profiling = True
options.profile_file_prefix = 'inputs/mocapgate_cuda_probe'
session = ort.InferenceSession(_download_yolox_onnx(), options, providers=['CUDAExecutionProvider'])
session.disable_fallback()
if 'CUDAExecutionProvider' not in session.get_providers():
    raise RuntimeError('GEM-X ONNX CUDA provider failed to load; CPU fallback is not a verified GPU setup.')
model_input = session.get_inputs()[0]
shape = [dimension if isinstance(dimension, int) and dimension > 0 else (3 if index == 1 else 640 if index > 1 else 1) for index, dimension in enumerate(model_input.shape)]
outputs = session.run(None, {model_input.name: np.zeros(shape, dtype=np.float32)})
torch.cuda.synchronize()
profile_file = Path(session.end_profiling())
profile = json.loads(profile_file.read_text())
if not all(np.isfinite(output).all() for output in outputs):
    raise RuntimeError('GEM-X CUDA detector returned non-finite values.')
if not any(event.get('args', {}).get('provider') == 'CUDAExecutionProvider' for event in profile):
    raise RuntimeError('GEM-X detector did not execute any nodes on CUDA.')
profile_file.unlink()
print('GEM-X CUDA detector execution OK')
''', cwd=repo)
    (home/'installed.json').write_text(json.dumps({'revision':REVISION}))
    print('MOCAPGATE_GEMX '+json.dumps({'gemx_dir':str(repo),'gemx_python':str(worker_py)}),flush=True)


if __name__=='__main__':main()
