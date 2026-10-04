"""Person identity, shared timing, independent exports and API selection."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch

from core import gvhmr, pipeline, report
from core.person_tracking import PoseTracker
from core.person_detector import suppress

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/studio"))
import server


def pose(x, raised=False):
    points = [[x, .2 + j / 60, 1] for j in range(33)]
    points[23] = [x-.03, .55, 1]
    points[24] = [x+.03, .55, 1]
    points[15] = [x-.15, .15 if raised else .6, 1]
    points[16] = [x+.15, .15 if raised else .6, 1]
    return {"image": points, "world": [[0, 0, 0, 1] for _ in range(33)]}


def person(pid, x, frames=12):
    return {"id": pid, "smpl_params_global": {
        "global_orient": [[0, 0, 0] for _ in range(frames)],
        "body_pose": [[0]*63 for _ in range(frames)],
        "transl": [[x, .9, f*.02] for f in range(frames)]}}


class Tracking(unittest.TestCase):
    def test_report_does_not_penalize_time_before_person_enters(self):
        landmarks = {'frames': [None]*4+[pose(.3)]*6+[None]*4}
        world = [[[0, 0, 0] for _ in range(22)] for _ in range(14)]
        result = report.analyze(world, 30, landmarks, active_range=(4, 9))
        items = {item['id']:item for item in result['items']}
        self.assertEqual(items['found']['value'], 1)
        self.assertEqual(items['gap']['value'], 0)
        self.assertEqual(len(result['per_frame']), 14)
        self.assertIsNone(result['per_frame'][0])
        self.assertIsNotNone(result['per_frame'][4])

    def test_object_boxes_remove_duplicate_partial_detections(self):
        boxes = [[.1, .1, .15, .6, .9], [.11, .1, .12, .3, .5],
                 [.65, .3, .2, .6, .8], [.66, .31, .19, .58, .6]]
        self.assertEqual(suppress(boxes), [boxes[0], boxes[2]])

    def test_occlusion_box_size_change_does_not_break_identity(self):
        tracker = PoseTracker()
        for f in range(8):
            p = pose(.3+f*.005)
            p['bbox'] = [.25+f*.005, .1, .12, .3 if f < 7 else .7]
            tracker.update([p])
        tracker.update([])
        tracker.update([])
        p = pose(.35); p['bbox'] = [.30, .2, .15, .3]
        tracker.update([p])
        self.assertEqual(len(tracker.results()), 1)
        self.assertIsNotNone(tracker.results()[0]['frames'][-1])

    def test_order_changes_and_short_occlusion(self):
        tracker = PoseTracker(max_gap=5)
        for f in range(6):
            a, b = pose(.2+f*.01), pose(.8-f*.01, True)
            tracker.update([b, a] if f % 2 else [a, b])
        tracker.update([pose(.74, True)])
        tracker.update([pose(.73, True), pose(.27)])
        tracks = tracker.results()
        self.assertEqual(len(tracks), 2)
        self.assertIsNone(tracks[0]["frames"][6])
        self.assertAlmostEqual(tracks[0]["frames"][7]["image"][23][0], .24)
        self.assertAlmostEqual(tracks[1]["frames"][7]["image"][23][0], .70)

    def test_crossing_preserves_distinct_pose_identity(self):
        tracker = PoseTracker()
        for f in range(11):
            a, b = pose(.2+f*.06), pose(.8-f*.06, True)
            tracker.update([b, a] if f % 2 else [a, b])
        tracks = tracker.results()
        self.assertEqual(len(tracks), 2)
        self.assertAlmostEqual(tracks[0]["frames"][-1]["image"][23][0], .77)
        self.assertAlmostEqual(tracks[1]["frames"][-1]["image"][23][0], .17)

    def test_expired_identity_is_not_reused(self):
        tracker = PoseTracker(max_gap=2)
        for _ in range(3): tracker.update([pose(.2)])
        for _ in range(4): tracker.update([])
        for _ in range(3): tracker.update([pose(.2)])
        self.assertEqual([p["id"] for p in tracker.results()], [1, 2])


class PeoplePipeline(unittest.TestCase):
    def test_scene_exports_independent_bvh_and_selected_save(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MOCAPGATE_HOME": tmp}):
            root = Path(tmp)
            source = root / "scene.json"
            source.write_text(json.dumps({"format": "mocapgate.scene/1", "fps": 30,
                                          "people": [person(3, -1), person(7, 1)]}), encoding="utf-8")
            take = pipeline.create_take(root / "takes", "duet", [source], "gvhmr-file")
            self.assertEqual(pipeline.process(take), 0)
            meta = pipeline.read_meta(take)
            self.assertEqual([p["id"] for p in meta["people"]], [3, 7])
            self.assertEqual([p["frames"] for p in meta["people"]], [12, 12])
            files = [(take / p["bvh"]).read_text() for p in meta["people"]]
            self.assertNotEqual(files[0], files[1])
            self.assertTrue(all("Frames: 12" in text for text in files))
            studio = server.Studio(root / "takes", "tok")
            info = studio.take_info(take.name)
            self.assertTrue(all(p["report"] for p in info["people"]))
            with patch.object(server, "downloads_dir", return_value=root), patch.object(server, "reveal"):
                saved = Path(studio.save_copy(take.name, "bvh", 7))
            self.assertEqual(saved.read_text(), files[1])
            with self.assertRaises(ValueError):
                studio.save_copy(take.name, "bvh", 99)
            selected = pipeline.person_meta({**meta, "fbx": "first.fbx"}, 7)
            self.assertIsNone(selected["fbx"])

    def test_rejects_duplicate_ids_and_unsynchronised_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "scene.json"
            for people in ([person(1, 0), person(1, 1)], [person(1, 0), person(2, 1, 8)],
                           [{**person(1, 0), "fps": 24}, {**person(2, 1), "fps": 30}]):
                source.write_text(json.dumps({"people": people}))
                with self.assertRaises(ValueError): gvhmr.load_people(str(source))

    def test_direct_cli_preserves_every_person(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scene.json"
            source.write_text(json.dumps({"fps": 24, "people": [person(2, -1), person(4, 1)]}))
            result = subprocess.run([sys.executable, str(pipeline.ROOT / "mocapgate.py"),
                                     str(source), "-o", str(root / "duet.bvh")], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs = sorted(root.glob("*.bvh"))
            self.assertEqual([p.name for p in outputs], ["duet_person_2.bvh", "duet_person_4.bvh"])
            self.assertNotEqual(outputs[0].read_text(), outputs[1].read_text())


if __name__ == "__main__":
    unittest.main()
