"""Bundle the tested Windows installer and portable setup into one downloadable ZIP."""
import argparse
from pathlib import Path
import zipfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portable',type=Path,required=True)
    parser.add_argument('--installer',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('dist'))
    args=parser.parse_args()
    if not args.installer.is_file():parser.error('Installer not found')
    args.out.mkdir(parents=True,exist_ok=True)
    name=args.portable.name.replace('-portable.zip','-windows-quickstart.zip')
    destination=args.out/name
    folder='MoCapGate-Windows/'
    launcher='@echo off\r\ncd /d "%~dp0"\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\setup_windows.ps1" -InstallerPath "%~dp0'+args.installer.name+'"\r\nif errorlevel 1 pause\r\n'
    with zipfile.ZipFile(args.portable) as source,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as target:
        for entry in source.infolist():
            parts=Path(entry.filename).parts
            if len(parts)<2 or '..' in parts or Path(entry.filename).is_absolute():raise ValueError('Unsafe portable archive entry')
            target.writestr(folder+'/'.join(parts[1:]),source.read(entry))
        target.write(args.installer,folder+args.installer.name)
        target.writestr(folder+'INSTALL.cmd',launcher)
        target.writestr(folder+'READ-ME.txt','Extract this complete ZIP, then double-click INSTALL.cmd. Internet is needed for initial Python/FFmpeg/MediaPipe setup. No GitHub account needed. Open Demo - Sports2D, two people in Studio and press Play. See docs/distribution.md for SMPL-X, Blender and setup details.\r\n')
    print(destination)

if __name__=='__main__':main()
