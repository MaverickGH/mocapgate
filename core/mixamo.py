"""Mixamo export names and fixed terminal joints; never invent terminal rotation."""
import copy
import re
from core.skeleton import Joint

def terminal_name(name):
    name=name.rsplit(':',1)[-1]
    if name=='Head':return 'HeadTop_End'
    if name in ('LeftToeBase','RightToeBase'):return name.replace('ToeBase','Toe_End')
    if re.fullmatch(r'(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)3',name):return name[:-1]+'4'
    return None

def prepare(root,frames,namespace=False,head_tip=None):
    root=copy.deepcopy(root);frames=copy.deepcopy(frames);added=[];renames={}
    def walk(j):
        for child in list(j.children):walk(child)
        base=j.name.rsplit(':',1)[-1];tip=terminal_name(base)
        if tip and not any(c.name.rsplit(':',1)[-1]==tip for c in j.children):
            offset=j.end_offset or (head_tip if base=='Head' else None)
            if offset is None and base=='Head':offset=(0.,10.,0.)
            if offset is not None:
                child=Joint(tip,tuple(offset),end_offset=(0.,0.,0.))
                j.children.append(child);j.end_offset=None;added.append(tip)
        renames[j.name]=('mixamorig:' if namespace else '')+base
        j.name=renames[j.name]
        for child in j.children:
            if child.name in added:child.name=('mixamorig:' if namespace else '')+child.name
    walk(root)
    for frame in frames:
        for name in added:frame[name]={'rot':(0.,0.,0.)}
        for name in list(frame):
            target=renames.get(name,('mixamorig:' if namespace else '')+name.rsplit(':',1)[-1])
            if target!=name:frame[target]=frame.pop(name)
    return root,frames
