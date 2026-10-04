#!/usr/bin/env python3
"""Add checked platform libraries beside public loaders without copying private implementations."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from native_packaging import CONFIG, LOADER, wrapper


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot', type=Path)
    ap.add_argument('packages', nargs='+', type=Path)
    args = ap.parse_args()
    root = args.snapshot.resolve()
    catalog = root / 'native-manifests'; catalog.mkdir(exist_ok=True)
    primary = json.loads((root / 'native-manifest.json').read_text())
    for package in args.packages:
        package = package.resolve()
        manifest = json.loads((package / 'native-manifest.json').read_text())
        if set(manifest['modules']) != set(CONFIG['modules']) or manifest['python'] != CONFIG['python']:
            raise RuntimeError('Incompatible package: '+str(package))
        target = manifest['system']+'-'+manifest['machine']
        is_primary = (manifest['system'],manifest['machine']) == (primary['system'],primary['machine'])
        for key,source in CONFIG['modules'].items():
            entry = manifest['modules'][key]
            library = (package / entry['library']).resolve()
            if not library.is_relative_to(package) or hashlib.sha256(library.read_bytes()).hexdigest() != entry['sha256']:
                raise RuntimeError('Invalid native library: '+target+'/'+key)
            if (package / source).read_text() != wrapper(key):
                raise RuntimeError('Original implementation in package: '+source)
            # Libraries stay beside their original loaders to preserve __file__-based resource paths.
            name = library.name if is_primary else target+'__'+library.name
            destination = root / Path(source).parent / name
            shutil.copy2(library,destination)
            entry['library'] = destination.relative_to(root).as_posix()
        (catalog / (target+'.json')).write_text(json.dumps(manifest,indent=2)+'\n')
        if is_primary:(root / 'native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (root / 'native_loader.py').write_text(LOADER)
    for key,source in CONFIG['modules'].items():
        if (root / source).read_text() != wrapper(key):raise RuntimeError('Altered public loader: '+source)
    print('Verified public library catalog:', ', '.join(p.stem for p in sorted(catalog.glob('*.json'))))

if __name__ == '__main__':main()
