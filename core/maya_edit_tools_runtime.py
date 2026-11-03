"""Maya-only correction tools. No automatic save, rebake or deletion of keys."""
from maya import cmds
from maya.api import OpenMaya as om


def joints():
    result = []
    for name in CONFIG['joints']:
        matches = [n for n in cmds.ls(type='joint', long=True) or []
                   if n.split('|')[-1].split(':')[-1] == name]
        if len(matches) != 1:
            raise RuntimeError('Open the exported character scene: missing or ambiguous joint ' + name)
        result.append(matches[0])
    return result


def check(*unused):
    nodes = joints()
    unit = cmds.currentUnit(query=True, time=True)
    fps = om.MTime(1, om.MTime.kSeconds).asUnits(om.MTime.uiUnit())
    times = cmds.keyframe(nodes, query=True, timeChange=True) or []
    off_grid = sorted(set(t for t in times if abs(t-round(t)) > 1e-5))
    message = 'Scene: %.6g FPS; expected %.6g FPS. Frames: 1–%d. Off-grid keys: %d.' % (fps, CONFIG['fps'], CONFIG['frames'], len(off_grid))
    if abs(fps-CONFIG['fps']) > .001:
        message += '\nFPS differs: reopen the exported scene before editing; changing FPS can retime existing work.'
    message += '\nUnits: ' + cmds.currentUnit(query=True, linear=True) + ' / ' + unit
    cmds.confirmDialog(title='MoCapGate — scene check', message=message, button=['OK'])


def correction_layer(*unused):
    nodes = joints()
    name = 'MoCapGate_Corrections'
    # Never reuse an unrelated pre-existing node or layer.
    if cmds.objExists(name):
        cmds.warning('MoCapGate_Corrections already exists. Select that layer in the Animation Layer editor.')
        return
    cmds.undoInfo(openChunk=True, chunkName='MoCapGate correction layer')
    try:
        layer = cmds.animLayer(name, override=False)
        for index, node in enumerate(nodes):
            attrs = ['rotateX', 'rotateY', 'rotateZ']
            if index == 0:
                attrs += ['translateX', 'translateY', 'translateZ']
            for attr in attrs:
                if not cmds.getAttr(node+'.'+attr, lock=True):
                    cmds.animLayer(layer, edit=True, attribute=node+'.'+attr)
        cmds.animLayer(layer, edit=True, preferred=True, selected=True)
    finally:
        cmds.undoInfo(closeChunk=True)
    cmds.warning('Correction layer ready. Keep it selected when keying; Save As to preserve the original export. Undo removes this setup.')


def select_part(part):
    nodes = joints()
    def matches(node):
        name = node.split('|')[-1].split(':')[-1].lower()
        return {'feet': 'foot' in name or 'toe' in name,
                'wrists': name.endswith('hand'),
                'fingers': any(p in name for p in ('thumb','index','middle','ring','pinky')),
                'all': True}[part]
    selected = [n for n in nodes if matches(n)]
    if selected:
        cmds.select(selected, replace=True)


def show():
    window = 'MoCapGateEditTools'
    if cmds.window(window, exists=True):
        cmds.deleteUI(window)
    cmds.window(window, title='MoCapGate — Maya finishing', widthHeight=(430, 260))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(label='Open the exported character scene first.\nCorrections use joints; this is not an IK/FK control rig.', align='left')
    cmds.button(label='Check scene FPS / integer keys', command=check)
    cmds.button(label='Create additive correction layer', command=correction_layer)
    for label, part in [('Select feet / toes','feet'), ('Select wrists','wrists'), ('Select fingers','fingers'), ('Select all character joints','all')]:
        cmds.button(label=label, command=lambda unused, part=part: select_part(part))
    cmds.text(label='Keep Corrections selected when keying. Save As a separate scene.', align='left')
    cmds.showWindow(window)
