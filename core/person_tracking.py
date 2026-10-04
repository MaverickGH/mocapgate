"""Associate pose detections with persistent IDs without third-party dependencies.

Uses predicted hip position, body scale and pose shape, with global assignment.
IDs are never reused. Long disappearances create a new track; identical people
crossing under complete occlusion cannot be reliably identified from poses alone.
"""
import math
from functools import lru_cache


def features(pose):
    if "bbox" in pose:
        x, y, w, h = pose["bbox"]
        return (x+w/2, y+h/2), max(.05, h)
    points = pose["image"]
    center = tuple((points[23][i] + points[24][i]) / 2 for i in (0, 1))
    visible = [p for p in points if p[2] >= 0.3] or points
    scale = max(0.05, max(p[1] for p in visible) - min(p[1] for p in visible))
    return center, scale


class PoseTracker:
    def __init__(self, max_gap=30):
        self.max_gap = max_gap
        self.tracks = []
        self.frame = 0

    def update(self, detections):
        if len(detections) > 8:
            raise ValueError("at most 8 people per frame")
        active = sorted((t for t in self.tracks if self.frame-t["last"] <= self.max_gap),
                        key=lambda t: t["last"], reverse=True)[:8]
        fs = [features(d) for d in detections]
        costs = []
        for track in active:
            age = self.frame-track["last"]
            predicted = [track["center"][i] + track["velocity"][i]*min(age, 6) for i in (0, 1)]
            row = []
            for detection, (center, scale) in zip(detections, fs):
                distance = math.dist(predicted, center)
                body_scale = max(scale, track["scale"])
                shape = []
                old = track["pose"]["image"]
                for j in (() if "bbox" in detection else (0, 11, 12, 15, 16, 25, 26, 27, 28)):
                    p, q = detection["image"][j], old[j]
                    if min(p[2], q[2]) > .3:
                        shape.append(math.dist([(p[i]-center[i])/scale for i in (0, 1)],
                                               [(q[i]-track["center"][i])/track["scale"] for i in (0, 1)]))
                row.append(distance/body_scale + .15*abs(math.log(scale/track["scale"])) +
                           .15*(sum(shape)/len(shape) if shape else 0)
                           if distance <= max(.12, body_scale*.7) else 100)
            costs.append(row)

        @lru_cache(None)
        def match(i, used):
            if i == len(active):
                return 0, ()
            score, tail = match(i+1, used)
            best = (.9+score, (-1,)+tail)
            for j, cost in enumerate(costs[i]):
                if not used & (1 << j) and cost < .9:
                    score, tail = match(i+1, used | (1 << j))
                    candidate = (cost+score, (j,)+tail)
                    if candidate[0] < best[0]:
                        best = candidate
            return best

        assigned = set()
        for track, j in zip(active, match(0, 0)[1]):
            if j >= 0:
                assigned.add(j)
                center, scale = fs[j]
                dt = self.frame-track["last"]
                # Box height changes under occlusion must not produce a huge
                # extrapolated velocity and disconnect the next observation.
                raw = [(center[i]-track["center"][i])/max(1, dt) for i in (0, 1)]
                track["velocity"] = [max(-.04, min(.04, .3*raw[i]+.7*track["velocity"][i]))
                                     if "bbox" in detections[j] else raw[i] for i in (0, 1)]
                track.update(center=center, scale=scale, pose=detections[j], last=self.frame)
                track["samples"][self.frame] = detections[j]
        for j, pose in enumerate(detections):
            if j not in assigned:
                center, scale = fs[j]
                self.tracks.append({"id": len(self.tracks)+1, "center": center, "scale": scale,
                                    "velocity": [0, 0], "pose": pose, "last": self.frame,
                                    "samples": {self.frame: pose}})
        self.frame += 1

    def results(self):
        minimum = min(3, self.frame)
        return [{"id": t["id"], "frames": [t["samples"].get(i) for i in range(self.frame)]}
                for t in self.tracks if len(t["samples"]) >= minimum]
