#!/usr/bin/env python3
"""Build native MoCapGate in isolation; never replace originals in the checkout."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'native-modules.json').read_text(encoding='utf-8'))
MARKER = '# MoCapGate native loader v1'

LOADER = '''"""Load a platform-specific library with the bundled CPython. See LICENSE."""
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
'''


def wrapper(key: str) -> str:
    if key == 'cli':
        return f'{MARKER}\nfrom native_loader import load\nif __name__ == "__main__":\n    raise SystemExit(load("{key}").main())\n'
    return f'{MARKER}\nimport sys\nfrom native_loader import load\nsys.modules[__name__] = load("{key}")\n'


def machine() -> str:
    value = platform.machine().lower()
    return {'aarch64': 'arm64', 'amd64': 'x86_64'}.get(value, value)


def python_path(folder: Path, system: str | None = None) -> Path:
    return folder / ('python/python.exe' if (system or sys.platform) == 'win32' else 'python/bin/python3.12')


def ignored(_folder, names):
    return [n for n in names if n in ('__pycache__', '.DS_Store') or n.startswith('._') or n.endswith(('.pyc', '.pyo'))]


def runtime_licences(destination: Path, work: Path) -> None:
    """Retain licence texts from the matching full upstream distribution."""
    import zstandard
    release = CONFIG['standalone_release']
    target = {'darwin': ('aarch64' if machine() == 'arm64' else 'x86_64') + '-apple-darwin',
              'win32': 'x86_64-pc-windows-msvc',
              'linux': ('aarch64' if machine() == 'arm64' else 'x86_64') + '-unknown-linux-gnu'}[sys.platform]
    prefix = f"cpython-{CONFIG['python']}+{release}-{target}-"
    request = urllib.request.Request('https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/'+release,
                                     headers={'User-Agent':'MoCapGate-native-packaging'})
    with urllib.request.urlopen(request, timeout=60) as response:
        assets = json.load(response)['assets']
    candidates = [a for a in assets if a['name'].startswith(prefix) and a['name'].endswith('-full.tar.zst')
                  and 'debug' not in a['name'] and 'freethreaded' not in a['name'] and 'static' not in a['name']]
    candidates.sort(key=lambda a: ('pgo+lto' not in a['name'], 'pgo' not in a['name'], a['name']))
    if not candidates: raise RuntimeError('Matching full Python distribution licences not found')
    asset = candidates[0]
    downloaded = work / 'python-full.tar.zst'
    urllib.request.urlretrieve(asset['browser_download_url'], downloaded)
    digest = hashlib.sha256(downloaded.read_bytes()).hexdigest()
    if asset.get('digest') and asset['digest'] != 'sha256:'+digest:
        raise RuntimeError('Python licence distribution checksum mismatch')
    folder = destination / 'python-licenses';folder.mkdir()
    with downloaded.open('rb') as compressed, zstandard.ZstdDecompressor().stream_reader(compressed) as reader:
        with tarfile.open(fileobj=reader, mode='r|') as tar:
            for entry in tar:
                if entry.isfile() and (entry.name == 'python/PYTHON.json' or Path(entry.name).name.startswith('LICENSE')):
                    data = tar.extractfile(entry).read()
                    relative = Path(entry.name)
                    if relative.is_absolute() or '..' in relative.parts: raise RuntimeError('Invalid upstream path')
                    target_file = folder / relative
                    target_file.parent.mkdir(parents=True, exist_ok=True);target_file.write_bytes(data)
    if not list(folder.rglob('LICENSE*')): raise RuntimeError('Python licence texts missing')
    (folder / 'provenance.json').write_text(json.dumps({'url':asset['browser_download_url'],'sha256':digest},indent=2)+'\n')


def runtime(destination: Path, work: Path) -> None:
    import uv
    uv_bin = Path(uv.find_uv_bin())
    env = {**os.environ, 'UV_PYTHON_INSTALL_DIR': str(work / 'interpreters'),
           'UV_PYTHON_BIN_DIR': str(work / 'bin'), 'UV_CACHE_DIR': str(work / 'uv-cache')}
    system = {'darwin': 'macos', 'win32': 'windows', 'linux': 'linux'}[sys.platform]
    arch = 'aarch64' if machine() == 'arm64' else 'x86_64'
    request = f'cpython-{CONFIG["python"]}-{system}-{arch}-{"gnu" if system == "linux" else "none"}'
    subprocess.run([str(uv_bin), 'python', 'install', request], env=env, check=True)
    interpreter = subprocess.check_output([str(uv_bin), 'python', 'find', '--managed-python', request], env=env, text=True).strip()
    prefix = Path(subprocess.check_output([interpreter, '-c', 'import sys; print(sys.base_prefix)'], text=True).strip())
    shutil.copytree(prefix, destination / 'python', ignore=ignored)
    runtime_licences(destination, work)
    # Headers, static link archives and Python tests are build resources, not runtime.
    for path in [destination / 'python/include', destination / 'python/lib/pkgconfig', destination / 'python/share/man']:
        if path.exists(): shutil.rmtree(path)
    for path in (destination / 'python').rglob('*.a'): path.unlink()
    for path in (destination / 'python').rglob('*'):
        if path.is_file() and path.suffix.lower() in ('.c', '.cpp', '.pyx', '.pdb', '.map'):
            path.unlink()
    shutil.copy2(uv_bin, destination / ('uv.exe' if os.name == 'nt' else 'uv'))
    licences = destination / 'uv-licenses'; licences.mkdir()
    distribution = importlib.metadata.distribution('uv')
    for file in distribution.files or []:
        if '/licenses/' in str(file):
            shutil.copy2(distribution.locate_file(file), licences / Path(file).name)
    subprocess.run([str(python_path(destination)), '-I', '-B', '-c',
                    'import ssl,venv,ensurepip; import sys; assert sys.version.split()[0] == '+repr(CONFIG['python'])], check=True)


def compile_modules(destination: Path, work: Path) -> dict:
    names = []
    for key, source in CONFIG['modules'].items():
        text = (ROOT / source).read_text(encoding='utf-8')
        if MARKER in text: raise RuntimeError('Original implementations are required; do not compile public loaders.')
        name = '_mocapgate_native_' + key
        (work / (name + '.py')).write_text(text, encoding='utf-8')
        names.append(name)
    setup = '''from setuptools import setup, Extension
from Cython.Build import cythonize
from Cython.Compiler import Options
Options.docstrings = False
setup(ext_modules=cythonize([Extension(n, [n+'.py'], extra_link_args=%r) for n in %r],
    compiler_directives={'language_level':3, 'binding':True, 'annotation_typing':False,
                        'infer_types':False, 'embedsignature':False, 'emit_code_comments':False}))
''' % (['/DEBUG:NONE'] if os.name == 'nt' else [], names)
    (work / 'setup.py').write_text(setup, encoding='utf-8')
    output = work / 'compiled'
    subprocess.run([sys.executable, 'setup.py', 'build_ext', '--build-lib', str(output)], cwd=work, check=True,
                   env={**os.environ, 'CFLAGS': '-O2 -g0' if os.name != 'nt' else ''})
    manifest = {}
    for key, source in CONFIG['modules'].items():
        name = '_mocapgate_native_' + key
        library = output / (name + sysconfig.get_config_var('EXT_SUFFIX'))
        if os.name != 'nt':
            strip = shutil.which('strip')
            if not strip: raise RuntimeError('strip is required to remove debug information')
            subprocess.run([strip, '-S' if sys.platform == 'darwin' else '--strip-debug', str(library)], check=True)
        target = destination / Path(source).parent / library.name
        shutil.copy2(library, target)
        (destination / source).write_text(wrapper(key), encoding='utf-8')
        manifest[key] = {'source': source, 'module': name, 'library': str(target.relative_to(destination)).replace(os.sep, '/'),
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (destination / 'native_loader.py').write_text(LOADER, encoding='utf-8')
    return manifest


def check(folder: Path) -> dict:
    manifest = json.loads((folder / 'native-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'mocapgate.native/1' or manifest.get('python') != CONFIG['python']:
        raise RuntimeError('Unsupported manifest/runtime version')
    if set(manifest['modules']) != set(CONFIG['modules']): raise RuntimeError('Protected module list does not match')
    for key, source in CONFIG['modules'].items():
        entry = manifest['modules'][key]
        if entry['source'] != source or (folder / source).read_text(encoding='utf-8') != wrapper(key):
            raise RuntimeError('Original or altered protected implementation: ' + source)
        library = (folder / entry['library']).resolve()
        if not library.is_relative_to(folder.resolve()): raise RuntimeError('Native library path escapes package')
        if hashlib.sha256(library.read_bytes()).hexdigest() != entry['sha256']: raise RuntimeError('Library checksum mismatch: '+key)
    for path in folder.rglob('*'):
        if path.name == '__pycache__' or path.name.endswith('.dSYM') or (path.is_file() and path.suffix.lower() in ('.c', '.cpp', '.pyx', '.pdb', '.map')):
            raise RuntimeError('Build or debug file in package: '+str(path.relative_to(folder)))
    if (folder / 'native_loader.py').read_text(encoding='utf-8') != LOADER: raise RuntimeError('Native loader modified')
    if not python_path(folder, manifest['system']).is_file(): raise RuntimeError('Bundled Python missing')
    if not (folder / 'python-licenses/provenance.json').is_file(): raise RuntimeError('Python licences/provenance missing')
    if not (folder / 'uv-licenses/LICENSE-MIT').is_file(): raise RuntimeError('uv licences missing')
    if not (folder / 'docs/licenses/Cython-LICENSE.txt').is_file(): raise RuntimeError('Cython licence missing')
    return manifest


def archive(folder: Path, output: Path) -> Path:
    check(folder)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and '.git' not in path.parts:
                z.write(path, path.relative_to(folder))
    return output


def build(destination: Path) -> Path:
    for name in ('Cython', 'setuptools', 'uv', 'zstandard'):
        key = 'cython' if name == 'Cython' else name
        if importlib.metadata.version(name) != CONFIG[key]: raise RuntimeError('Install requirements-native.txt')
    if platform.python_version() != CONFIG['python']: raise RuntimeError('Build Python must be '+CONFIG['python'])
    if destination.exists(): raise RuntimeError('Choose a new output folder; existing packages are never overwritten')
    import make_portable
    if not (ROOT / 'apps/studio/ui/vendor/three/build/three.module.js').is_file():
        subprocess.run([sys.executable, str(ROOT / 'scripts/vendor_web.py')], check=True)
    destination.mkdir(parents=True)
    for relative in make_portable.INCLUDE + ['native-modules.json', 'AGENTS.md', 'scripts/native_packaging.py', 'scripts/check_public_snapshot.py', 'scripts/make_portable.py', 'tests/test_bundle.py', 'tests/test_native_package.py']:
        source = ROOT / relative; target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir(): shutil.copytree(source, target, ignore=ignored)
        else: shutil.copy2(source, target)
    with tempfile.TemporaryDirectory(prefix='mocapgate-native-') as temporary:
        work = Path(temporary)
        runtime(destination, work)
        modules = compile_modules(destination, work)
    manifest = {'format':'mocapgate.native/1', 'python':CONFIG['python'], 'abi':sys.implementation.cache_tag,
                'system':sys.platform, 'machine':machine(), 'modules':modules}
    (destination / 'native-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (destination / 'START.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexport PATH="$PWD:$PATH"\nexport PYTHONDONTWRITEBYTECODE=1\nexec ./python/bin/python3.12 ./mocapgate.py studio "$@"\n')
    (destination / 'START.sh').chmod(0o755)
    (destination / 'START_WINDOWS.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\nset "PATH=%CD%;%PATH%"\r\nset PYTHONDONTWRITEBYTECODE=1\r\n"%~dp0python\\python.exe" "%~dp0mocapgate.py" studio %*\r\n')
    check(destination)
    return destination


def snapshot(package: Path, destination: Path) -> Path:
    check(package)
    if destination.exists(): raise RuntimeError('Choose a new public snapshot folder')
    files = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'], cwd=ROOT).decode().split('\0')
    destination.mkdir(parents=True)
    for relative in set(filter(None, files)):
        source = ROOT / relative
        if not source.is_file() or relative in CONFIG['modules'].values(): continue
        # Private source-build workflow must never run in the public repository.
        if relative.startswith('.github/workflows/'): continue
        target = destination / relative;target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(source,target)
    workflow = destination / '.github/workflows/native-check.yml'
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("""name: public-native-check
on: [push, pull_request, workflow_dispatch]
jobs:
  verify:
    # This preview contains only macOS ARM64 artifacts. Add independently tested targets before expanding.
    runs-on: macos-15
    env:
      PYTHONDONTWRITEBYTECODE: '1'
    steps:
      - uses: actions/checkout@v4
      - run: python/bin/python3.12 -B scripts/native_packaging.py check .
      - run: python/bin/python3.12 -B tests/test_native_package.py .
""", encoding='utf-8')
    # Runtime and native libraries are copied from a checked package, not rebuilt from loaders.
    shutil.copytree(package, destination, dirs_exist_ok=True, ignore=ignored)
    # Prebuilt offline web assets are required in a published snapshot, unlike source checkouts.
    gitignore = destination / '.gitignore'
    gitignore.write_text(gitignore.read_text().replace('apps/studio/ui/vendor/\n', ''), encoding='utf-8')
    cli = 'python\\python.exe mocapgate.py' if os.name == 'nt' else 'python/bin/python3.12 mocapgate.py'
    for name, notice in [('README.md', '> **Нативный снимок: '+sys.platform+' / '+machine()+'.** Используйте START.sh / START_WINDOWS.cmd или встроенный Python. Выбранные реализации заменены библиотеками. [Подробности](docs/code-protection.ru.md).\n\n'),
                         ('README.en.md', '> **Native snapshot: '+sys.platform+' / '+machine()+'.** Use START.sh / START_WINDOWS.cmd or the bundled Python. Selected implementations are native libraries. [Details](docs/code-protection.en.md).\n\n')]:
        readme = destination / name
        content = readme.read_text(encoding='utf-8').replace('python3 mocapgate.py', cli)
        content = content.replace('Этот репозиторий содержит исходники.', 'Этот снимок содержит нативные библиотеки и исходники интеграций.')
        content = content.replace('This repository contains source code.', 'This snapshot contains native libraries and integration sources.')
        readme.write_text(notice+content, encoding='utf-8')
    (destination / 'PUBLIC-SNAPSHOT.md').write_text('Native public snapshot. Originals are kept in a separate local development checkout.\nThis preview supports '+sys.platform+' / '+machine()+'. Use its bundled Python.\nOther target packages require their own native builds before publication.\nNo history rewrite or remote publication has been performed.\n', encoding='utf-8')
    check(destination)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command', required=True)
    b=sub.add_parser('build');b.add_argument('--out',type=Path,required=True)
    c=sub.add_parser('check');c.add_argument('folder',type=Path)
    z=sub.add_parser('zip');z.add_argument('folder',type=Path);z.add_argument('--out',type=Path,required=True)
    s=sub.add_parser('snapshot');s.add_argument('package',type=Path);s.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='build':print(build(args.out.resolve()))
    elif args.command=='check':check(args.folder.resolve());print('Native package contents and checksums: OK')
    elif args.command=='zip':print(archive(args.folder.resolve(),args.out.resolve()))
    else:print(snapshot(args.package.resolve(),args.out.resolve()))

if __name__=='__main__':main()
