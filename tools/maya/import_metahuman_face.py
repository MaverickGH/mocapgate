"""Import GUI curves onto an already assembled MetaHuman in Maya.

In Maya's Python Script Editor load this file, then call:
import_face('/absolute/path/person.metahuman.json', namespace='Ada', start_frame=1)
No geometry, DNA, or RigLogic plugin is installed by this script.
"""
import json
import math
from pathlib import Path


def import_face(path, namespace='', start_frame=1):
    import maya.cmds as cmds
    import maya.api.OpenMaya as om

    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('format') != 'mocapgate.metahuman-face/1':
        raise ValueError('Not a MoCapGate MetaHuman face animation')
    fps = float(data['fps'])
    if not math.isfinite(fps) or fps <= 0 or not math.isfinite(start_frame):
        raise ValueError('Invalid fps or start frame')
    prefix = namespace.strip(':') + ':' if namespace else ''
    plugs = {name: prefix + name for name in data['channels']}
    invalid = [plug for plug in plugs.values() if not cmds.objExists(plug)
               or not cmds.getAttr(plug, settable=True)]
    if invalid:
        raise ValueError('Missing, locked or connected controls: ' + ', '.join(invalid))
    for frame in data['frames']:
        if frame is not None:
            if set(frame) != set(plugs) or not all(math.isfinite(float(v)) for v in frame.values()):
                raise ValueError('Invalid curve frame')
    step = om.MTime(1. / fps, om.MTime.kSeconds).asUnits(om.MTime.uiUnit())
    if not cmds.undoInfo(query=True, state=True):
        raise ValueError('Enable Maya Undo before importing animation')
    cmds.undoInfo(openChunk=True, chunkName='MoCapGate MetaHuman face')
    failed = False
    wrote_keys = False
    try:
        for index, frame in enumerate(data['frames']):
            for name, plug in plugs.items():
                # Explicit neutral keys prevent interpolation across lost-face gaps.
                value = 0. if frame is None else frame[name]
                cmds.setKeyframe(plug, time=start_frame + index * step, value=value,
                                 inTangentType='linear', outTangentType='linear')
                wrote_keys = True
    except Exception:
        failed = True
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
        if failed and wrote_keys:
            cmds.undo()
    return {'frames': len(data['frames']), 'controls': len(plugs),
            'mapping_status': data.get('mapping_status')}
