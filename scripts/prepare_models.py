"""Prefetch and validate optional hand/face models for offline local capture."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from core.components import MediaPipe

mp = MediaPipe()
mp.fetch_detector()
for kind in ('hand', 'face'):
    mp.fetch_detail(kind)
check = '''
import sys
from mediapipe.tasks.python import vision
from mediapipe.tasks import python as tasks
with vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(base_options=tasks.BaseOptions(model_asset_path=sys.argv[1]),num_hands=2)):
    pass
with vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=tasks.BaseOptions(model_asset_path=sys.argv[2]),num_faces=1,output_face_blendshapes=True)):
    pass
print('Hand and face models ready')
'''
subprocess.run([str(mp.python()), '-c', check, str(mp.detail_path('hand')), str(mp.detail_path('face'))], check=True)
