"""Real footage: corrected crop detections and preserved rejected baseline."""
import gzip
import hashlib
import json
import unittest

from core.person_tracking import PoseTracker
from tools.check_multi_person_video import FIXTURE, evaluate_tracks


class RealVideo(unittest.TestCase):
    def test_fixture_integrity(self):
        expected = json.loads((FIXTURE / "expected.json").read_text())
        self.assertEqual(hashlib.sha256((FIXTURE / expected["video"]).read_bytes()).hexdigest(),
                         expected["sha256"])
        data = json.loads(gzip.decompress((FIXTURE / "detections.json.gz").read_bytes()))
        self.assertEqual(len(data["detections"]), expected["frames"])
        self.assertEqual(data["fps"], expected["fps"])

    def test_two_real_people_keep_their_identity(self):
        expected = json.loads((FIXTURE / "expected.json").read_text())
        data = json.loads(gzip.decompress((FIXTURE / "crop_detections.json.gz").read_bytes()))
        tracker = PoseTracker(max_gap=30)
        for poses in data["detections"]:
            tracker.update(poses)
        result = evaluate_tracks({**data, "people": tracker.results()}, expected)
        self.assertTrue(result["passed"], result["failures"])

    def test_legacy_duplicate_poses_are_rejected_by_acceptance(self):
        expected = json.loads((FIXTURE / "expected.json").read_text())
        data = json.loads(gzip.decompress((FIXTURE / "detections.json.gz").read_bytes()))
        tracker = PoseTracker(max_gap=30)
        for poses in data['detections']:
            tracker.update(poses)
        self.assertFalse(evaluate_tracks({**data, 'people': tracker.results()}, expected)['passed'])


if __name__ == "__main__":
    unittest.main()
