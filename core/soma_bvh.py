"""Export SOMA's actual rest skeleton and local bind-relative rotations."""
import re
from core.skeleton import Joint
from core.rotations import axis_angle_to_matrix,matrix_to_euler_zxy,continuous_euler
from core.video_timing import resample_person


def convert(payload,target,duration):
    names=[re.sub(r'[^A-Za-z0-9_]','_',n) for n in payload['names']]
    if len(set(names))!=len(names):raise ValueError('SOMA joint names must be unique')
    parents=payload['parents'];rest=payload['rest']
    if parents[0]!=-1 or any(p>=i or p < -1 for i,p in enumerate(parents)):
        raise ValueError('Unsupported SOMA parent order')
    nodes=[Joint(name,(0,0,0)) for name in names]
    for i,p in enumerate(parents):
        if p>=0:
            nodes[i].offset=tuple(100*(rest[i][k]-rest[p][k]) for k in range(3));nodes[p].children.append(nodes[i])
    for n in nodes:
        if not n.children:n.end_offset=(0,0,0)
    pose=payload['poses'];person={'fps':payload['fps'],'params':{'global_orient':[p[0] for p in pose],
          'body_pose':[sum(p[1:],[]) for p in pose],'transl':payload['positions']}}
    params=resample_person(person,target,duration)['params']
    frames=[];previous={}
    for f,body in enumerate(params['body_pose']):
        rotations=[params['global_orient'][f]]+[body[j:j+3] for j in range(0,len(body),3)]
        frame={}
        for name,rv in zip(names,rotations):
            e=continuous_euler(matrix_to_euler_zxy(axis_angle_to_matrix(rv)),previous.get(name));previous[name]=e;frame[name]={'rot':e}
        frame[names[0]]['pos']=tuple(v*100 for v in params['transl'][f]);frames.append(frame)
    return nodes[0],frames
