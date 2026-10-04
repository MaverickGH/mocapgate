#!/usr/bin/env python3
"""Verify an unpacked native archive with its interpreter, never system Python."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def main():
    from native_packaging import archive, check, python_path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('package', type=Path)
    ap.add_argument('--require-blender', action='store_true')
    args = ap.parse_args()
    package = args.package.resolve()
    check(package)
    with tempfile.TemporaryDirectory(prefix='mocapgate-native-test-') as tmp:
        tmp = Path(tmp)
        packed = archive(package, tmp / 'native.zip')
        unpacked = tmp / 'unpacked'
        with zipfile.ZipFile(packed) as z:
            z.extractall(unpacked)
            if os.name != 'nt':
                for entry in z.infolist():
                    mode = entry.external_attr >> 16
                    if mode: (unpacked / entry.filename).chmod(mode)
        check(unpacked)
        py = str(python_path(unpacked))
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONIOENCODING':'utf-8',
               'MOCAPGATE_HOME':str(tmp / 'config'), 'MOCAPGATE_LIBRARY':str(tmp / 'takes'),
               'PATH': str(unpacked) + (os.pathsep + str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32') if os.name == 'nt' else '')}
        env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
        def run(*argv, success=True):
            result = subprocess.run([py, '-B', *map(str, argv)], cwd=unpacked, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
            if (result.returncode == 0) != success:
                raise RuntimeError(result.stdout)
            return result.stdout
        run('-c', "import shutil; assert shutil.which('python') is None and shutil.which('python3') is None; from native_loader import load; load('cli')")
        import platform
        arch = {'aarch64':'arm64','amd64':'x86_64'}.get(platform.machine().lower(),platform.machine().lower())
        catalog = unpacked / 'native-manifests' / (sys.platform+'-'+arch+'.json')
        manifest_path = catalog if catalog.is_file() else unpacked / 'native-manifest.json'
        saved_manifest = manifest_path.read_text()
        mismatched = json.loads(saved_manifest);mismatched['abi'] = 'cpython-incompatible'
        manifest_path.write_text(json.dumps(mismatched))
        error = run('mocapgate.py', '--help', success=False)
        assert 'matching OS/architecture' in error
        manifest_path.write_text(saved_manifest)
        print(run(ROOT / 'tests/test_bundle.py', unpacked), end='')
        run('mocapgate.py', '--demo', tmp / 'demo.bvh')
        assert 'MOTION' in (tmp / 'demo.bvh').read_text()
        source = tmp / 'walk.mocapgate.json'
        source.write_text(json.dumps({'smpl_params_global': {'global_orient':[[0,0,0]]*12,
            'body_pose':[[0.0]*63]*12, 'transl':[[0,0.9,0]]*12}}))
        run('mocapgate.py', 'new', source, '--name', 'native-test')
        take = next((tmp / 'takes').iterdir())
        run('mocapgate.py', 'process', take)
        meta = json.loads((take / 'take.json').read_text())
        assert (take / meta['bvh']).is_file()
        run('mocapgate.py', tmp / 'missing.json', '-o', tmp / 'missing.bvh', success=False)
        assert not (tmp / 'missing.bvh').exists()
        run('-c', """import sys,time; sys.path.insert(0,'apps/studio'); import server
j=server.Job('native-cancel',[sys.executable,'-B','-c','import time; time.sleep(120)'],'test')
try:
    j.cancel()
    deadline=time.monotonic()+15
    while j.code is None and time.monotonic()<deadline: time.sleep(0.05)
    assert j.cancelled and j.code is not None
finally:
    if j.code is None: j.cancel()
""")
        blender = run('-c', 'from core.components import find_blender; print(find_blender() or "")').strip()
        if blender:
            run('mocapgate.py', 'process', take, '--fbx')
            meta = json.loads((take / 'take.json').read_text())
            assert (take / meta['fbx']).stat().st_size > 100
            print('Blender FBX export: OK')
        elif args.require_blender:
            raise RuntimeError('Blender required for export verification')
        else:
            print('Blender unavailable: FBX test skipped (release still requires target export testing)')
        # Test copies run against the unpacked libraries, not the original implementations.
        shutil.copytree(ROOT / 'tests', unpacked / 'tests', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
        suite_env = {**env, 'PATH':os.environ.get('PATH','')}
        subprocess.run([py, '-B', '-m', 'unittest', 'discover', 'tests'], cwd=unpacked, env=suite_env, check=True, timeout=180)
        print('Native archive: startup without system Python, processing, errors, cancellation and unit suite OK')
    return 0

if __name__ == '__main__': raise SystemExit(main())
