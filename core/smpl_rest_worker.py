"""Compute licensed model rest joints in the user's model environment, not Studio Python."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.smpl import rest_from_model

if __name__ == '__main__':
    model, source, output = sys.argv[1:]
    betas = json.loads(Path(source).read_text())
    Path(output).write_text(json.dumps(rest_from_model(model, betas)))
