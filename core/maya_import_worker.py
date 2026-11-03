"""Executed inside Maya: native scene import, bind-aware rig transfer and baking."""
import json
import math
import runpy
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om


def rotation(node):
    matrix = om.MMatrix(cmds.xform(node, query=True, worldSpace=True, matrix=True))
    return om.MTransformationMatrix(matrix).rotation(asQuaternion=True).asMatrix()


def run(config_path):
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    cmds.file(new=True, force=True)
    rig = config.get('rig')
    if rig:
        cmds.file(rig, i=True, type='mayaAscii', namespace='character', ignoreVersion=True, executeScriptNodes=False)
    cmds.currentUnit(time=config['unit'], updateAnimation=False)
    cmds.file(config['scene'], i=True, type='mayaAscii', namespace='capture', ignoreVersion=True, executeScriptNodes=False)
    cmds.currentUnit(time=config['unit'], updateAnimation=False)
    source = cmds.ls('capture:*', type='joint', long=True)
    targets = cmds.ls('character:*', type='joint', long=True) if rig else source
    if rig:
        source_by_name = {j.split('|')[-1].split(':')[-1]: j for j in source}
        target_by_name = {j.split('|')[-1].split(':')[-1]: j for j in targets}
        pair_joints = runpy.run_path(str(Path(__file__).with_name('maya_export.py')))['rig_joint_pairs']
        profile=config.get('profile')
        if profile:
            missing=[(s,t) for s,t in profile['mapping'].items() if s not in source_by_name or t not in target_by_name]
            if missing: raise ValueError('Profile joints missing: '+str(missing))
            if len(source_by_name)!=len(source) or len(target_by_name)!=len(targets): raise ValueError('Ambiguous joint names in rig')
            pairs=[(source_by_name[s],target_by_name[t]) for s,t in profile['mapping'].items()]
        else:
            pairs = pair_joints(source_by_name, target_by_name)
        if len(pairs) < (1 if profile else 20):
            raise ValueError('Rig must contain the MoCapGate/Mixamo joint names')
        # Maya matrices use row vectors. Transfer motion relative to each bind
        # orientation; copying Euler channels would break wrist/finger axes.
        target_rest = {j: rotation(j) for _,j in pairs}
        roots = [j for j in source if not cmds.listRelatives(j, parent=True, type='joint')]
        duplicates = [cmds.duplicate(j, returnRootsOnly=True, inputConnections=False)[0] for j in roots]
        neutral = {}
        for root in duplicates:
            for j in [root] + (cmds.listRelatives(root, allDescendents=True, type='joint', fullPath=True) or []):
                cmds.setAttr(j+'.rotate', 0,0,0)
        # A duplicate may be renamed by Maya; topology order is authoritative.
        def ordered(root):
            out=[root]
            for child in cmds.listRelatives(root, children=True, type='joint', fullPath=True) or []:
                out += ordered(child)
            return out
        for root, duplicate in zip(roots, duplicates):
            neutral.update({s: rotation(d) for s,d in zip(ordered(root),ordered(duplicate))})
        cmds.delete(duplicates)
        for frame in range(1, config['frames']+1):
            cmds.currentTime(frame)
            # Parents first; world rotations preserve the target's bone lengths.
            for s,t in sorted(pairs, key=lambda pair: pair[1].count('|')):
                world = target_rest[t] * neutral[s].inverse() * rotation(s)
                yaw = float((profile or {}).get('yaw',0))
                yaw_matrix = om.MEulerRotation(0,math.radians(yaw),0).asMatrix()
                world = world * yaw_matrix
                transform = om.MTransformationMatrix(world)
                position = cmds.xform(t, query=True, worldSpace=True, translation=True)
                if not cmds.listRelatives(t, parent=True, type='joint'):
                    position = cmds.xform(s, query=True, worldSpace=True, translation=True)
                    vector = om.MVector(*position) * float((profile or {}).get('scale',1))
                    vector = vector * yaw_matrix
                    position = list(vector)
                transform.setTranslation(om.MVector(*position), om.MSpace.kTransform)
                cmds.xform(t, worldSpace=True, matrix=list(transform.asMatrix()))
                cmds.setKeyframe(t, attribute=['rotateX','rotateY','rotateZ'] + (['translateX','translateY','translateZ'] if t in [p[1] for p in pairs if not cmds.listRelatives(p[1],parent=True,type='joint')] else []), time=frame)
        cmds.delete(roots)
    curves = cmds.listConnections(targets, type='animCurve', source=True, destination=False) or []
    rotate_curves = [c for c in set(curves) if cmds.nodeType(c)=='animCurveTA']
    if rotate_curves:
        cmds.filterCurve(rotate_curves, filter='euler')
    cmds.bakeResults(targets, time=(1,config['frames']), sampleBy=1, simulation=True,
                     sparseAnimCurveBake=False, preserveOutsideKeys=False,
                     attribute=['rotateX','rotateY','rotateZ','translateX','translateY','translateZ'])
    cmds.currentUnit(time=config['unit'], updateAnimation=False)
    cmds.playbackOptions(min=1,max=config['frames'],animationStartTime=1,animationEndTime=config['frames'])
    cmds.currentTime(1)
    cmds.file(rename=config['output'])
    cmds.file(save=True,type='mayaAscii')
