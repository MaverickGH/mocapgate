"""Optional hand/face inference in the MediaPipe environment, using body-ID hints.

Missing detections remain null; each crop must match the nearest body wrist/head.
Face z is relative image depth, not metric world position.
"""
import argparse
import json
import math
from contextlib import ExitStack


def owner(point, hints, key):
    candidates = []
    for pid, hint in hints:
        for side, target in hint.get(key, {}).items():
            distance = math.dist(point[:2], target[:2]) / max(1, target[2])
            if distance < 1:
                candidates.append((distance, pid, side))
    candidates.sort()
    if not candidates or (len(candidates) > 1 and candidates[1][0] < candidates[0][0]*1.2 + .05):
        return None
    return candidates[0][1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('hints'); ap.add_argument('out')
    ap.add_argument('--hand-model'); ap.add_argument('--face-model')
    args = ap.parse_args()
    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks import python as tasks
    data = json.load(open(args.hints, encoding='utf-8'))
    length = data['frames']
    result = {**{k: data[k] for k in ('fps', 'width', 'height')},
              'format': 'mocapgate.details/1', 'face_depth': 'relative-image',
              'feet': 'heel-and-toe-only; no individual toe detection',
              'people': [{'id': p['id'], 'frames': [None]*length} for p in data['people']]}
    output = {p['id']: p['frames'] for p in result['people']}
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError('Cannot open video')
    def crop(rgb, target):
        x, y, radius = target
        height, width = rgb.shape[:2]
        left, top = max(0, int(x-radius)), max(0, int(y-radius))
        right, bottom = min(width, int(x+radius)), min(height, int(y+radius))
        if right-left < 12 or bottom-top < 12:
            return None
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb[top:bottom,left:right]))
        return image, left, top, right-left, bottom-top
    with ExitStack() as stack:
        hands = stack.enter_context(vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=tasks.BaseOptions(model_asset_path=args.hand_model), num_hands=2))) if args.hand_model else None
        face = stack.enter_context(vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=tasks.BaseOptions(model_asset_path=args.face_model), num_faces=1,
            output_face_blendshapes=True, output_facial_transformation_matrixes=True))) if args.face_model else None
        for i in range(length):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f'Video ended at frame {i}; expected {length}')
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hints = [(p['id'], p['hints'][i]) for p in data['people'] if p['hints'][i]]
            for pid, hint in hints:
                detail = {'hands': {}, 'face': None}
                if hands:
                    for side, target in hint.get('wrists', {}).items():
                        c = crop(rgb, target)
                        if c is None: continue
                        image, x, y, w, h = c
                        prediction = hands.detect(image)
                        matches = []
                        for j, points in enumerate(prediction.hand_landmarks):
                            pixels = [[round(x+p.x*w, 3), round(y+p.y*h, 3), round(p.z*w, 3)] for p in points]
                            if owner(pixels[0], hints, 'wrists') != (pid, side): continue
                            world = [[p.x, p.y, p.z] for p in prediction.hand_world_landmarks[j]]
                            matches.append((math.dist(pixels[0][:2], target[:2]), {'image': pixels, 'world': world,
                                'score': prediction.handedness[j][0].score}))
                        if matches: detail['hands'][side] = min(matches, key=lambda v: v[0])[1]
                if face and hint.get('head'):
                    target = hint['head']['face']; c = crop(rgb, target)
                    if c:
                        image, x, y, w, h = c; prediction = face.detect(image)
                        if prediction.face_landmarks:
                            points = prediction.face_landmarks[0]
                            pixels = [[round(x+p.x*w, 3), round(y+p.y*h, 3), round(p.z*w, 3)] for p in points]
                            if owner(pixels[1], hints, 'head') == (pid, 'face'):
                                detail['face'] = {'image': pixels,
                                    'blendshapes': {b.category_name: b.score for b in prediction.face_blendshapes[0]},
                                    'crop_transform': prediction.facial_transformation_matrixes[0].tolist()}
                output[pid][i] = detail if detail['hands'] or detail['face'] else None
            if i % 15 == 0:
                print(json.dumps({'stage': 'details', 'progress': i/max(1,length), 'message': 'Кисти и лицо…'}, ensure_ascii=True), flush=True)
    cap.release()
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, separators=(',', ':'))


if __name__ == '__main__':
    main()
