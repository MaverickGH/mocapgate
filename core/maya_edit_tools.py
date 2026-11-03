"""Explicitly run Maya helper; never embedded as a scene script node."""
from pathlib import Path


def write(destination, names, fps, frames):
    config = {'joints': list(names), 'fps': fps, 'frames': frames}
    runtime = Path(__file__).with_name('maya_edit_tools_runtime.py').read_text(encoding='utf-8')
    Path(destination).write_text('# MoCapGate — run in Maya Script Editor / Python after opening character.ma\nCONFIG = ' + repr(config) + '\n' + runtime + '\nshow()\n', encoding='utf-8')
    return Path(destination).name
