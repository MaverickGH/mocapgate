"""Windows CLI and worker output must survive legacy console encodings."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from core import pipeline

ROOT = Path(__file__).resolve().parents[1]


class OutputEncoding(unittest.TestCase):
    def test_doctor_with_legacy_console_encoding(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "mocapgate.py"), "doctor"],
            env={**os.environ, "PYTHONIOENCODING": "cp1251"},
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("✓ Python", result.stdout.decode("utf-8"))

    def test_worker_events_preserve_russian(self):
        event = {"stage": "pose", "message": "поза найдена"}
        script = "import json; print(json.dumps(" + repr(event) + ", ensure_ascii=False))"
        output = io.StringIO()
        with patch.dict(os.environ, {"PYTHONIOENCODING": "cp1251"}), contextlib.redirect_stdout(output):
            code, lines = pipeline._run_streaming([sys.executable, "-c", script], "pose")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(lines[0]), event)
        self.assertEqual(json.loads(output.getvalue()), event)
