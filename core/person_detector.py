"""Detect people at full-frame and square-tile scales, then suppress duplicates.

MediaPipe's pose detector can report duplicate poses of one person. An independent
object detector supplies one crop per person; pose inference runs separately.
"""
import math


def suppress(boxes, threshold=.4):
    kept = []
    for box in sorted(boxes, key=lambda b: b[4], reverse=True):
        x, y, w, h, _ = box
        duplicate = False
        for a, b, c, d, _ in kept:
            intersection = max(0, min(x+w, a+c)-max(x, a)) * max(0, min(y+h, b+d)-max(y, b))
            if (intersection / max(1e-12, w*h+c*d-intersection) > threshold or
                    intersection / max(1e-12, min(w*h, c*d)) > .85):
                duplicate = True
                break
        if not duplicate:
            kept.append(box)
    return kept


class PersonDetector:
    def __init__(self, model):
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        self.mp = mp
        self.detector = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
            base_options=mpt.BaseOptions(model_asset_path=model), category_allowlist=['person'],
            score_threshold=.25, max_results=16))

    def detect(self, rgb, maximum):
        height, width = rgb.shape[:2]
        regions = [(0, 0, width, height)]
        # Keep small people large enough for the detector, with overlapping tiles
        # so a person at a tile boundary still has a complete detection.
        side = min(width, height)
        if max(width, height) > side*1.25:
            length = max(width, height)
            count = math.ceil((length-side)/(side*.75))+1
            for i in range(count):
                start = round(i*(length-side)/(count-1))
                regions.append((start, 0, side, side) if width > height else (0, start, side, side))
        boxes = []
        import numpy as np
        for x, y, w, h in regions:
            image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                                  data=np.ascontiguousarray(rgb[y:y+h, x:x+w]))
            for detection in self.detector.detect(image).detections:
                box = detection.bounding_box
                boxes.append([box.origin_x+x, box.origin_y+y, box.width, box.height,
                              detection.categories[0].score])
        return suppress(boxes)[:maximum]

    def close(self):
        self.detector.close()
