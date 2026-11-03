"""Regenerate data-only Man_Rig preview after an intentional rig asset update."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.character_rig import read_asset, ASSET

if __name__ == '__main__':
    asset=read_asset()
    ASSET.parent.mkdir(parents=True,exist_ok=True)
    ASSET.write_text(json.dumps(asset,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(ASSET)
