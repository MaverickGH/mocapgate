"""A recipient can install the supplied sample with no repository login or models."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_sample_install_is_complete_and_preserves_existing_take(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            command = [sys.executable, str(ROOT/'scripts/install_example.py'), str(ROOT), '--library', tmp]
            subprocess.run(command, check=True, capture_output=True, env=env)
            take = Path(tmp)/'sample-sports2d-two-people'
            meta = json.loads((take/'take.json').read_text(encoding='utf-8'))
            self.assertEqual([p['id'] for p in meta['people']], [1, 2])
            self.assertEqual(meta['frames'], 230)
            self.assertGreater((take/meta['video']).stat().st_size, 1000000)
            for person in meta['people']:
                for key in ('bvh', 'overlay', 'report_file', 'capture_file'):
                    self.assertTrue((take/person[key]).is_file())
                self.assertIn('Frames: 230', (take/person['bvh']).read_text())
            (take/'take.json').write_text('user-edit', encoding='utf-8')
            subprocess.run(command, check=True, capture_output=True, env=env)
            self.assertEqual((take/'take.json').read_text(), 'user-edit')
