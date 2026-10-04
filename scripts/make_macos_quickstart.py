"""Bundle one architecture's DMG with the portable, per-user installer helpers."""
import argparse
from pathlib import Path
import zipfile

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--portable',type=Path,required=True)
    ap.add_argument('--dmg',type=Path,required=True)
    ap.add_argument('--arch',choices=('arm64','x64'),required=True)
    ap.add_argument('--out',type=Path,default=Path('dist'))
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    name=args.portable.name.replace('-portable.zip',f'-macos-{args.arch}-quickstart.zip')
    destination=args.out/name;folder='MoCapGate-Mac/'
    with zipfile.ZipFile(args.portable) as source,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as target:
        for entry in source.infolist():
            parts=Path(entry.filename).parts
            if len(parts)<2 or '..' in parts or Path(entry.filename).is_absolute():raise ValueError('Unsafe portable archive entry')
            info=zipfile.ZipInfo(folder+'/'.join(parts[1:]));info.create_system=entry.create_system;info.external_attr=entry.external_attr;info.compress_type=zipfile.ZIP_DEFLATED
            target.writestr(info,source.read(entry))
        target.write(args.dmg,folder+args.dmg.name)
        info=zipfile.ZipInfo(folder+'INSTALL.command');info.create_system=3;info.external_attr=0o100755<<16
        target.writestr(info,'#!/bin/bash\ncd "$(dirname "$0")"\nexec bash scripts/setup_macos.sh "$@"\n')
        target.writestr(folder+'READ-ME.txt',f'Architecture: {args.arch}. Extract this complete ZIP, then open INSTALL.command. Internet is needed for initial Python/FFmpeg/MediaPipe setup. No GitHub account needed. Builds are unsigned; macOS may require manual approval in Privacy & Security. Open Demo - Sports2D, two people in Studio and press Play. See docs/distribution.md for details.\n')
    print(destination)

if __name__=='__main__':main()
