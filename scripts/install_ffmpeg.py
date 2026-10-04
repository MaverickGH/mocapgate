"""Copy the imageio-ffmpeg platform binary into the per-user tools directory."""
import os
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

if not shutil.which('ffmpeg'):
    directory = Path(os.environ.get('MOCAPGATE_TOOLS_DIR', str(Path.home() / '.local/bin')))
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    subprocess.run([str(destination), '-version'], check=True, stdout=subprocess.DEVNULL)
    print('FFmpeg installed:', destination)
else:
    print('FFmpeg already available:', shutil.which('ffmpeg'))
