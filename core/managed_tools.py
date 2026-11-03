"""Per-user tools: verified downloads, no global PATH edits or administrator rights."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from core import settings

BLENDER_VERSION = '4.5.9'
BLENDER_URL = 'https://download.blender.org/release/Blender4.5/'


def home():
    from core.components import HOME
    return HOME / 'tools'


def ffmpeg_path():
    return home() / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')


def find_ffmpeg():
    managed = ffmpeg_path()
    return str(managed) if managed.is_file() else shutil.which('ffmpeg')


def download(url, destination, digest, log=print):
    """An interrupted or corrupt download never becomes an installed file; network failures resume."""
    from core.install_util import fetch
    fetch(url, destination, digest, log=log)


def pick(items, condition, what):
    """next() без StopIteration: пустое сообщение об ошибке ничего не объясняет."""
    for item in items:
        if condition(item):
            return item
    raise RuntimeError(what)


def install_ffmpeg(log=print):
    current = find_ffmpeg()
    if current:
        try:
            subprocess.run([current, '-version'], check=True, capture_output=True, timeout=30)
            log('FFmpeg: готов / ready')
            return 0
        except (OSError, subprocess.SubprocessError):
            pass
    architecture = platform.machine().lower()
    arm = architecture in ('arm64', 'aarch64')
    tags = {'darwin': 'macosx_11_0_arm64' if arm else 'macosx_10_9_intel.macosx_10_9_x86_64',
            'win32': 'win_amd64', 'linux': 'manylinux2014_aarch64' if arm else 'manylinux2014_x86_64'}
    if sys.platform not in tags or (sys.platform == 'win32' and arm):
        raise RuntimeError('FFmpeg: unsupported platform')
    with urllib.request.urlopen('https://pypi.org/pypi/imageio-ffmpeg/0.6.0/json', timeout=60) as response:
        metadata = json.load(response)
    filename = 'imageio_ffmpeg-0.6.0-py3-none-' + tags[sys.platform] + '.whl'
    entry = pick(metadata['urls'], lambda item: item['filename'] == filename, 'FFmpeg: на PyPI нет сборки ' + filename)
    directory = home()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as folder:
        wheel = Path(folder) / filename
        download(entry['url'], wheel, entry['digests']['sha256'], log)
        with zipfile.ZipFile(wheel) as archive:
            binaries = [name for name in archive.namelist() if name.startswith('imageio_ffmpeg/binaries/ffmpeg-')]
            if len(binaries) != 1:
                raise ValueError('Unexpected FFmpeg wheel contents')
            candidate = Path(folder) / ffmpeg_path().name
            with archive.open(binaries[0]) as source, candidate.open('wb') as target:
                shutil.copyfileobj(source, target)
            candidate.chmod(0o755)
            subprocess.run([str(candidate), '-version'], check=True, capture_output=True, timeout=30)
            candidate.replace(ffmpeg_path())
            licenses = directory / 'ffmpeg-licenses'
            licenses.mkdir(exist_ok=True)
            for name in archive.namelist():
                if 'license' in name.lower() or name.endswith('METADATA'):
                    (licenses / Path(name).name).write_bytes(archive.read(name))
    log('FFmpeg: готов / ready')
    return 0


def install_blender(log=print):
    from core.components import find_blender
    existing = find_blender()
    if existing:
        try:
            subprocess.run([existing, '--background', '--factory-startup', '--version'], check=True, capture_output=True, timeout=60)
            log('Blender: готов / ready')
            return 0
        except (OSError, subprocess.SubprocessError):
            pass
    arm = platform.machine().lower() in ('arm64', 'aarch64')
    target = {'darwin': 'macos-arm64.dmg' if arm else 'macos-x64.dmg',
              'win32': 'windows-arm64.zip' if arm else 'windows-x64.zip',
              'linux': 'linux-x64.tar.xz'}.get(sys.platform)
    if not target or (sys.platform == 'linux' and arm):
        raise RuntimeError('Blender: unsupported platform')
    filename = f'blender-{BLENDER_VERSION}-{target}'
    with urllib.request.urlopen(urllib.request.Request(BLENDER_URL + f'blender-{BLENDER_VERSION}.sha256', headers={'User-Agent':'Mozilla/5.0 MoCapGate/0.3.3'}), timeout=60) as response:
        lines = response.read().decode().splitlines()
    digest = pick(lines, lambda line: line.split() and line.split()[-1].lstrip('*') == filename,
                  'Blender: нет контрольной суммы для ' + filename).split()[0]
    destination = home() / 'blender' / BLENDER_VERSION
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        folder = Path(folder)
        archive = folder / filename
        download(BLENDER_URL + filename, archive, digest, log)
        extracted = folder / 'extracted'
        extracted.mkdir()
        if sys.platform == 'darwin':
            mount = folder / 'mount'
            subprocess.run(['hdiutil', 'attach', str(archive), '-nobrowse', '-readonly', '-mountpoint', str(mount)], check=True, capture_output=True, timeout=600)
            try:
                shutil.copytree(mount / 'Blender.app', extracted / 'Blender.app', symlinks=True)
            finally:
                # Ошибка отключения образа не должна скрывать настоящую причину сбоя.
                for force in ([], ['-force']):
                    try:
                        if subprocess.run(['hdiutil', 'detach', str(mount)] + force, capture_output=True, timeout=120).returncode == 0:
                            break
                    except (OSError, subprocess.SubprocessError):
                        pass
            binary = extracted / 'Blender.app/Contents/MacOS/Blender'
        elif sys.platform == 'win32':
            with zipfile.ZipFile(archive) as zipped:
                for name in zipped.namelist():
                    if not (extracted / name).resolve().is_relative_to(extracted.resolve()):
                        raise ValueError('Unsafe Blender archive path')
                zipped.extractall(extracted)
            binary = pick(extracted.glob('*/blender.exe'), bool, 'Blender: в архиве нет blender.exe')
        else:
            with tarfile.open(archive) as compressed:
                compressed.extractall(extracted, filter='data')
            binary = pick(extracted.glob('*/blender'), bool, 'Blender: в архиве нет blender')
        subprocess.run([str(binary), '--background', '--factory-startup', '--version'], check=True, capture_output=True, timeout=60)
        relative = binary.relative_to(extracted)
        if destination.exists():
            shutil.rmtree(destination)
        extracted.replace(destination)
        settings.save({'blender': str(destination / relative)})
    log('Blender: готов / ready')
    return 0


def install_recommended(model='heavy', log=print):
    log('[1/3] FFmpeg')
    install_ffmpeg(log)
    log('[2/3] FFprobe')
    install_ffprobe(log)
    log('[3/3] Blender · FBX export')
    install_blender(log)
    log('Инструменты экспорта готовы / Export tools ready.')
    return 0


def install_smplx(log=print):
    """CPU model runtime also works on Macs without a GVHMR CUDA environment."""
    from core.components import HOME
    uv = shutil.which('uv')
    if not uv:
        raise RuntimeError('Use the native Studio distribution with bundled uv.')
    directory = HOME / 'smplx' / 'venv'
    from core.install_util import ensure_venv, host_python
    python = ensure_venv(directory, lambda: subprocess.run([uv, 'venv', '-p', host_python('3.12'), str(directory)], check=True), log)
    check = subprocess.run([str(python), '-c', 'import numpy,torch,smplx; assert numpy.__version__ == "1.26.4"'], capture_output=True)
    if check.returncode:
        log('SMPL-X: installing CPU model tools / устанавливаю обработку модели…')
        torch = '2.2.2' if sys.platform == 'darwin' and platform.machine().lower() in ('x86_64', 'amd64') else '2.5.1'
        command = [uv, 'pip', 'install', '-p', str(python), 'numpy==1.26.4', 'smplx==0.1.28', 'torch==' + torch]
        if sys.platform != 'darwin':
            command += ['--index', 'https://download.pytorch.org/whl/cpu', '--index-strategy', 'unsafe-best-match']
        subprocess.run(command, check=True)
        subprocess.run([str(python), '-c', 'import numpy,torch,smplx; print(torch.__version__)'], check=True)
    settings.save({'model_python': str(python)})
    log('SMPL-X tools: готово / ready')
    return 0


def model_runtime(cfg):
    """Prefer the explicitly configured CUDA runtime; otherwise use CPU tools."""
    if cfg.get('gvhmr_python'):
        return cfg
    return {**cfg, 'gvhmr_python': cfg.get('model_python', ''), 'gvhmr_wsl': ''}


def install_ffprobe(log=print):
    """Install probe alongside managed tools; keep vendor licences with the archive."""
    target=home()/('ffprobe.exe' if os.name=='nt' else 'ffprobe')
    if target.is_file():return str(target)
    existing=shutil.which('ffprobe')
    if existing:return existing
    if os.name=='nt':
        url='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
        with urllib.request.urlopen(url+'.sha256',timeout=60) as response:digest=response.read().decode().split()[0]
    elif sys.platform=='linux':
        with urllib.request.urlopen('https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest',timeout=60) as response:data=json.load(response)
        tag='linuxarm64' if platform.machine().lower() in ('aarch64','arm64') else 'linux64'
        asset=pick(data['assets'],lambda a:tag+'-gpl' in a['name'] and a['name'].endswith('.tar.xz') and '-shared' not in a['name'],'ffprobe: нет сборки '+tag+' в последнем релизе BtbN')
        url=asset['browser_download_url'];digest=asset['digest'].split(':',1)[1]
    elif sys.platform=='darwin':
        arm=platform.machine().lower() in ('arm64','aarch64')
        url='https://www.osxexperts.net/'+('ffprobe9arm.zip' if arm else 'ffprobe80intel.zip')
        digest='0c94fbdd8917022f28115eca512196cf4648732bc9e5db9ec8896c7e519d02aa' if arm else '0b6576104a95c1b39d4939e2df86f8f7cf1d55287ff57da48777d94605d12feb'
    else:
        raise RuntimeError('ffprobe: unsupported platform')
    home().mkdir(parents=True,exist_ok=True)
    archive=home()/('ffprobe-vendor.zip' if sys.platform in ('win32','darwin') else 'ffprobe-vendor.tar.xz')
    download(url,archive,digest,log)
    try:
        with tempfile.TemporaryDirectory(dir=home()) as folder:
            tmp=Path(folder)/target.name
            if sys.platform in ('win32','darwin'):
                with zipfile.ZipFile(archive) as z:
                    member=pick(z.namelist(),lambda n:Path(n).name==target.name and not n.startswith('__MACOSX/'),'ffprobe: нет '+target.name+' в архиве')
                    with z.open(member) as source,tmp.open('wb') as out:shutil.copyfileobj(source,out)
            else:
                with tarfile.open(archive) as z:
                    member=pick(z.getmembers(),lambda n:n.name.endswith('/bin/ffprobe'),'ffprobe: нет bin/ffprobe в архиве')
                    with z.extractfile(member) as source,tmp.open('wb') as out:shutil.copyfileobj(source,out)
            tmp.chmod(0o755)
            subprocess.run([str(tmp),'-version'],capture_output=True,check=True,timeout=30)
            tmp.replace(target)
    finally:
        archive.unlink(missing_ok=True)
    return str(target)
