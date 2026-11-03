"""Install unchanged, redistributable MediaPipe models from the native package."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'pose_landmarker_heavy.task', 'hand_landmarker.task', 'face_landmarker.task'}


def install(destination, log=print):
    destination = Path(destination)
    if destination.name not in NAMES:
        return False
    folder = ROOT / 'assets/models/mediapipe'
    manifest = folder / 'manifest.json'
    if not manifest.is_file():
        return False  # Older packages retain their normal download path.
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('format') != 'mocapgate.mediapipe-models/1':
        raise ValueError('Invalid bundled model manifest; reinstall the complete package.')
    entry = data['models'].get(destination.name)
    if entry is None:
        return False
    source = folder / destination.name
    if not source.is_file() or source.stat().st_size != entry['size']:
        raise ValueError('Bundled model missing or incomplete: ' + destination.name)
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != entry['sha256']:
        raise ValueError('Bundled model checksum mismatch: ' + destination.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.part')
    shutil.copyfile(source, temporary)
    temporary.replace(destination)
    log('Модель из установочного пакета / Bundled model: ' + destination.name)
    return True
