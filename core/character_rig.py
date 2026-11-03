"""Bounded, non-executing reader and retargeter for the bundled Man_Rig scene.

This is not a general Maya interpreter. Custom control rigs still need Maya.
All transforms here are column-vector matrices; Maya stores row matrices.
"""
from array import array
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from core.maya_export import rig_joint_pairs, time_unit
from core.rotations import (axis_angle_to_matrix, continuous_euler,
    euler_zxy_to_matrix, matmul, mat_vec, matrix_to_euler_zxy,
    matrix_to_quat, quat_to_matrix, transpose)

ROOT = Path(__file__).resolve().parents[1]
RIG = ROOT / 'assets/rigs/Man_Rig.ma'
ASSET = ROOT / 'apps/studio/ui/rigs/man-rig.json'
IDENTITY = ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def maya_xyz(values):
    """Maya XYZ row order becomes Rz * Ry * Rx for column vectors."""
    axes = [axis_angle_to_matrix([math.radians(v) if i == j else 0 for j in range(3)])
            for i,v in enumerate(values)]
    return matmul(axes[2], matmul(axes[1], axes[0]))


def numbers(text):
    result = [float(v) for v in text.split()]
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Non-finite rig values')
    return result


def node_vector(body, name, default=(0.,0.,0.)):
    match = re.search(r'setAttr\s+"\.'+name+r'"\s+-type "double3"\s+([^;]+);', body)
    result = numbers(match[1]) if match else list(default)
    if len(result) != 3: raise ValueError('Invalid joint vector')
    return result


def indexed(body, attr, width):
    rows = {}
    for match in re.finditer(r'setAttr\s+"\.'+attr+r'\[(\d+)(?::(\d+))?\]"\s+(?:-type "[^"]+"\s+)?([^;]+);',body):
        first = int(match[1]); last = int(match[2] or first)
        values = numbers(match[3])
        if len(values) != (last-first+1)*width: raise ValueError('Invalid '+attr+' array')
        rows.update((i,values[(i-first)*width:(i-first+1)*width]) for i in range(first,last+1))
    if not rows or set(rows) != set(range(len(rows))): raise ValueError('Incomplete '+attr+' array')
    return [rows[i] for i in range(len(rows))]


def read_asset(path=RIG):
    """Extract data only; never execute file commands or embedded scripts."""
    raw = Path(path).read_bytes()
    if len(raw)>16*1024*1024: raise ValueError('Rig scene too large')
    text = raw.decode('utf-8')
    if re.search(r'createNode (script|ikHandle|constraint|expression)\b',text):
        raise ValueError('Only the prepared FK skin rig is supported')
    blocks = list(re.finditer(r'createNode (\w+) -n "([^"]+)"(?: -p "([^"]+)")?;([\s\S]*?)(?=\ncreateNode |\Z)',text))
    joints = [b for b in blocks if b[1]=='joint']
    names = [b[2] for b in joints]
    if len(names)!=len(set(names)) or not 20<=len(names)<=200: raise ValueError('Invalid rig joints')
    indices = {n:i for i,n in enumerate(names)}
    bones = []; world = []
    for i,b in enumerate(joints):
        parent = indices.get(b[3],-1)
        if (i==0 and parent!=-1) or (i>0 and not 0<=parent<i): raise ValueError('Unsupported rig hierarchy')
        if any(abs(v-1)>1e-5 for v in node_vector(b[4],'s',(1,1,1))) or any(node_vector(b[4],'ra')):
            raise ValueError('Scaled/rotate-axis joints need Maya')
        orient = maya_xyz(node_vector(b[4],'jo'))
        bind = re.search(r'setAttr "\.bps" -type "matrix"\s+([^;]+);',b[4])
        if bind:
            values = numbers(bind[1])
            if len(values)!=16: raise ValueError('Invalid bind matrix')
            rotation = quat_to_matrix(matrix_to_quat(tuple(tuple(values[c*4+r] for c in range(3)) for r in range(3))))
            position = values[12:15]
        else:
            rotation = matmul(world[parent][0],orient) if parent>=0 else orient
            local = node_vector(b[4],'t')
            position = [world[parent][1][k]+mat_vec(world[parent][0],local)[k] for k in range(3)] if parent>=0 else local
        # Maya's saved matrices have six significant digits. Keep that precision
        # consistent across the preview and export instead of mixing rest poses.
        local_rotation = matmul(transpose(world[parent][0]),rotation) if parent>=0 else rotation
        local_position = mat_vec(transpose(world[parent][0]),[position[k]-world[parent][1][k] for k in range(3)]) if parent>=0 else position
        bones.append({'name':b[2],'parent':parent,'position':local_position,
                      'rotation':local_rotation,'orient':orient,'world_rotation':rotation})
        world.append((rotation,position))
    mesh = next(b[4] for b in blocks if b[1]=='mesh' and b[2]=='BodyShapeOrig')
    vertices = indexed(mesh,'vt',3); edges = indexed(mesh,'ed',3)
    faces=[]
    for command in re.finditer(r'setAttr "\.fc\[[^\]]+\]"([\s\S]*?);',mesh):
        for match in re.finditer(r'\bf (\d+)\s+([\d\s-]+)(?=\bmu\b|\bf\b|$)',command[1]):
            ids = [int(v) for v in match[2].split()]
            if len(ids)!=int(match[1]) or not 3<=len(ids)<=8: raise ValueError('Unsupported polygon')
            polygon = [int(edges[e][0] if e>=0 else edges[-e-1][1]) for e in ids]
            if any(v<0 or v>=len(vertices) for v in polygon): raise ValueError('Invalid polygon vertex')
            faces.extend([polygon[0],polygon[j],polygon[j+1]] for j in range(1,len(polygon)-1))
    if not faces: raise ValueError('No rig faces')
    skin = next(b[4] for b in blocks if b[1]=='skinCluster')
    inverse_bind = indexed(skin,'pm',16)
    influences={int(m[2]):indices[m[1]] for m in re.finditer(r'connectAttr "([^"]+)\.wm" "skinCluster1\.ma\[(\d+)\]";',text)}
    if set(influences)!=set(range(len(inverse_bind))): raise ValueError('Incomplete skin influences')
    weights={}
    for m in re.finditer(r'setAttr "\.wl\[(\d+)(?::(\d+))?\]\.w"\s+([^;]+);',skin):
        values=m[3].split(); cursor=0
        for vertex in range(int(m[1]),int(m[2] or m[1])+1):
            count=int(values[cursor]);cursor+=1; row=[]
            if not 1<=count<=64: raise ValueError('Invalid influence count')
            for _ in range(count):
                index=int(values[cursor]);weight=float(values[cursor+1]);cursor+=2
                if index not in influences or not math.isfinite(weight) or weight<0: raise ValueError('Invalid skin weight')
                row.append([index,weight])
            # Maya may split one vertex's sparse weight array across commands.
            weights.setdefault(vertex,{}).update(row)
        if cursor!=len(values): raise ValueError('Invalid skin weight range')
    if set(weights)!=set(range(len(vertices))): raise ValueError('Incomplete skin weights')
    normalized=[]
    for i in range(len(vertices)):
        total=sum(weights[i].values())
        if abs(total-1)>1e-4:raise ValueError(f'Incomplete skin weights for vertex {i}')
        normalized.append([[j,w/total] for j,w in sorted(weights[i].items())])
    return {'format':'mocapgate.character-geometry/1','source_sha256':hashlib.sha256(raw).hexdigest(),
        'name':'Man_Rig','bones':bones,'vertices':vertices,'faces':faces,
        'influences':[influences[i] for i in range(len(inverse_bind))],
        'inverse_bind':inverse_bind,'weights':normalized}


def read_bvh(path):
    """Read MoCapGate's own exported BVH, including the final SMPL-X skeleton."""
    text=Path(path).read_text(encoding='utf-8'); header,motion=text.split('MOTION',1)
    tokens=re.findall(r'[{}]|[^\s{}]+',header);cursor=0; names=[]; parents=[]; offsets=[];channels=[]
    def joint(parent):
        nonlocal cursor
        kind=tokens[cursor];cursor+=1
        name=tokens[cursor];cursor+=1
        if tokens[cursor]!='{':raise ValueError('Invalid BVH')
        cursor+=1
        if kind=='End':
            while tokens[cursor]!='}':cursor+=1
            cursor+=1;return
        index=len(names);names.append(name.split(':')[-1]);parents.append(parent)
        if tokens[cursor]!='OFFSET':raise ValueError('Missing BVH offset')
        offsets.append(tuple(map(float,tokens[cursor+1:cursor+4])));cursor+=4
        if tokens[cursor]!='CHANNELS':raise ValueError('Missing BVH channels')
        count=int(tokens[cursor+1]);channels.append(tokens[cursor+2:cursor+2+count]);cursor+=2+count
        while tokens[cursor]!='}':joint(index)
        cursor+=1
    cursor=1 if tokens[0]=='HIERARCHY' else 0;joint(-1)
    lines=motion.strip().splitlines();count=int(lines[0].split(':')[1]);step=float(lines[1].split(':')[1])
    rows=[numbers(line) for line in lines[2:] if line.strip()]
    if count!=len(rows) or not count or not math.isfinite(step) or step<=0 or len(set(names))!=len(names):raise ValueError('Invalid BVH timeline')
    if any(len(row)!=sum(map(len,channels)) for row in rows):raise ValueError('Invalid BVH frame')
    return names,parents,offsets,channels,rows,step


def build(bvh, destination, fps):
    """Save a skinned Maya character and compact bone motion for Studio."""
    asset=json.loads(ASSET.read_text(encoding='utf-8'))
    if asset['source_sha256']!=hashlib.sha256(RIG.read_bytes()).hexdigest(): raise ValueError('Rig preview asset is stale')
    names,parents,offsets,channels,rows,step=read_bvh(bvh)
    if abs(1/step-fps)>1e-3:raise ValueError('FPS персонажа и записи не совпадают — обработайте дубль заново')
    bones=asset['bones']; mapping={target:source for source,target in rig_joint_pairs({n:i for i,n in enumerate(names)},{b['name']:i for i,b in enumerate(bones)})}
    if len(mapping)<20:raise ValueError('Скелет записи не подходит к Man_Rig: выберите в Настройках «скелет записи» или свою модель')
    destination=Path(destination); binary=destination.with_suffix('.f32'); info=destination.with_suffix('.rig.json')
    curves=[[array('d') for _ in range(3)] for _ in bones];translations=[array('d') for _ in range(3)];previous={}
    with binary.open('wb') as stream:
        for row in rows:
            source=[];root_position=None;cursor=0
            for i,cs in enumerate(channels):
                values=dict(zip(cs,row[cursor:cursor+len(cs)]));cursor+=len(cs)
                if not set(cs)<=set(('Xposition','Yposition','Zposition','Zrotation','Xrotation','Yrotation')):raise ValueError('Unsupported BVH channels')
                if [c for c in cs if c.endswith('rotation')]!=['Zrotation','Xrotation','Yrotation']:raise ValueError('Unsupported BVH rotation order')
                local=euler_zxy_to_matrix(values['Zrotation'],values['Xrotation'],values['Yrotation'])
                source.append(matmul(source[parents[i]],local) if parents[i]>=0 else local)
                if i==0:root_position=[values.get(c,0) for c in ('Xposition','Yposition','Zposition')]
            target_world=[];packed=array('f',root_position)
            for axis,value in enumerate(root_position):translations[axis].append(value)
            for i,b in enumerate(bones):
                parent=b['parent']
                world=matmul(source[mapping[i]],b['world_rotation']) if i in mapping else matmul(target_world[parent],b['rotation'])
                local=matmul(transpose(target_world[parent]),world) if parent>=0 else world
                target_world.append(world)
                w,x,y,z=matrix_to_quat(local);packed.extend((x,y,z,w))
                # Maya JO precedes its channel rotation in column form. YXZ row
                # channels match MoCapGate's ZXY column-vector Euler convention.
                channel=matmul(transpose(b['orient']),local)
                angles=continuous_euler(matrix_to_euler_zxy(channel),previous.get(i));previous[i]=angles
                for axis,value in enumerate(angles):curves[i][axis].append(value)
            if sys.byteorder!='little':packed.byteswap()
            packed.tofile(stream)
    scene=RIG.read_text(encoding='utf-8')
    scene=re.sub(r'currentUnit[^;]+;',f'currentUnit -l centimeter -a degree -t {time_unit(fps)};',scene,count=1)
    with destination.open('w',encoding='utf-8') as stream:
        stream.write(scene+'\n// MoCapGate character animation; original skin and mesh retained.\n')
        for i,b in enumerate(bones):
            name=b['name'];stream.write(f'select -ne "{name}";\nsetAttr ".ro" 4;\nsetAttr ".s" -type "double3" 1 1 1;\n')
            stream.write('setAttr ".t" -type "double3" '+' '.join(f'{v:.12g}' for v in b['position'])+';\n')
            axes=[('rz',curves[i][0]),('rx',curves[i][1]),('ry',curves[i][2])]
            if i==0:axes += list(zip(('tx','ty','tz'),translations))
            for attr,values in axes:
                curve='mocapgate_'+name+'_'+attr
                stream.write(f'createNode animCurveT{"L" if attr.startswith("t") else "A"} -n "{curve}";\nsetAttr ".tan" 2;\n')
                stream.write(f'setAttr -s {len(values)} ".ktv[0:{len(values)-1}]" '+' '.join(f'{j+1} {v:.12g}' for j,v in enumerate(values))+';\n')
                stream.write(f'connectAttr -f "{curve}.o" "{name}.{attr}";\n')
        stream.write(f'playbackOptions -min 1 -max {len(rows)} -ast 1 -aet {len(rows)};\ncurrentTime 1;\n')
    info.write_text(json.dumps({'format':'mocapgate.character-motion/1','name':'Man_Rig',
        'fps':fps,'frames':len(rows),'bone_count':len(bones),'stride':3+4*len(bones),
        'motion_file':binary.name,'geometry_url':'/ui/rigs/man-rig.json'},separators=(',',':')),encoding='utf-8')
    from core.maya_edit_tools import write as write_edit_tools
    tools = write_edit_tools(destination.with_suffix('.maya-tools.py'), [b['name'] for b in bones], fps, len(rows))
    return {'character_scene':destination.name,'character_motion':info.name,'maya_tools':tools}
