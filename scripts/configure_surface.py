"""Connect the user's own licensed model without replacing an existing GVHMR runtime."""
import os
import sys
sys.path.insert(0, sys.argv[1])
from core import settings
cfg = settings.load()
changes = {"smplx_model": os.environ["MOCAPGATE_SETUP_MODEL"]}
if not cfg.get("gvhmr_python"):
    changes["gvhmr_python"] = os.environ["MOCAPGATE_SETUP_SURFACE_PYTHON"]
settings.save(changes)
