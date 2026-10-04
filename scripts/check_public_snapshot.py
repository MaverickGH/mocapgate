#!/usr/bin/env python3
"""Reject a public Git push containing original protected implementations."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from native_packaging import CONFIG, wrapper, LOADER


def check_commit(sha):
    def blob(path):
        return subprocess.check_output(['git','show',sha+':'+path],stderr=subprocess.DEVNULL)
    manifest=json.loads(blob('native-manifest.json'))
    if blob('native_loader.py').decode() != LOADER: raise RuntimeError('Altered native loader')
    for required in ('apps/studio/ui/vendor/three/build/three.module.js', 'apps/studio/ui/vendor/tasks-vision/vision_bundle.mjs', 'LICENSE', 'python-licenses/provenance.json'):
        blob(required)
    if set(manifest['modules'])!=set(CONFIG['modules']):raise RuntimeError('Incomplete protected module list')
    for key,source in CONFIG['modules'].items():
        if blob(source).decode()!=wrapper(key):raise RuntimeError('Protected source would be published: '+source)
        entry=manifest['modules'][key]
        if entry['source'] != source: raise RuntimeError('Manifest source mismatch: '+key)
        path=Path(entry['library'])
        if path.is_absolute() or '..' in path.parts:raise RuntimeError('Invalid library path')
        if hashlib.sha256(blob(entry['library'])).hexdigest()!=entry['sha256']:raise RuntimeError('Native checksum mismatch: '+key)
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',sha]).decode().splitlines()
    for catalog in (name for name in names if name.startswith('native-manifests/') and name.endswith('.json')):
        target=json.loads(blob(catalog))
        if set(target['modules']) != set(CONFIG['modules']): raise RuntimeError('Incomplete platform catalog: '+catalog)
        for key,source in CONFIG['modules'].items():
            entry=target['modules'][key]
            path=Path(entry['library'])
            if entry['source'] != source or path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Invalid platform entry: '+catalog)
            if hashlib.sha256(blob(entry['library'])).hexdigest() != entry['sha256']:
                raise RuntimeError('Platform library checksum mismatch: '+catalog)

    for name in names:
        if name.endswith(('.c','.cpp','.pyx','.pdb','.map')) or '.dSYM/' in name or '__pycache__' in name:
            raise RuntimeError('Build/debug output would be published: '+name)


def main():
    try:
        for line in sys.stdin:
            local_ref,local_sha,remote_ref,remote_sha=line.split()
            if set(local_sha)=={'0'}:continue
            if 'local-development' in local_ref:raise RuntimeError('Local development branch cannot be pushed')
            # Check the complete reachable history, not only a clean-looking tip.
            commits=subprocess.check_output(['git','rev-list',local_sha]).decode().splitlines()
            for sha in commits:check_commit(sha)
    except (RuntimeError,subprocess.CalledProcessError,ValueError,KeyError) as exc:
        print('Public push blocked: '+str(exc),file=sys.stderr)
        print('Use a reviewed Git snapshot with no original protected history.',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
