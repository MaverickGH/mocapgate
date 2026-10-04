"""Retarget observed hands onto the exact SMPL-X rest skeleton."""
import copy
import math
from core import smpl
from core.rotations import (axis_angle_to_matrix, frame_from_axes, mat_vec, matmul,
                            transpose, swing, matrix_to_axis_angle, matrix_to_euler_zxy, continuous_euler)
from core.hand_bvh import palm_points
from core.skeleton import Joint

NAMES=list(smpl.NAMES)+['Jaw','LeftEye','RightEye']
for side in ('Left','Right'):
    for finger in ('Index','Middle','Pinky','Ring','Thumb'):
        NAMES.extend(f'{side}Hand{finger}{i}' for i in (1,2,3))


def globals_for(go,bp):
    local=[go]+[bp[i*3:i*3+3] for i in range(21)]; result=[]
    for i,p in enumerate(smpl.PARENTS):
        r=axis_angle_to_matrix(local[i]);result.append(r if p<0 else matmul(result[p],r))
    return result


def hands(params, details, rest, parents):
    """Use hand palm orientation in camera space; finger axes come from SMPL-X."""
    output=copy.deepcopy(params);n=len(params['transl'])
    inc=params.get('incam') or (params if params.get('cam_to_yup') else None)
    for key in ('left_hand_pose','right_hand_pose'):output[key]=[[0.]*45 for _ in range(n)]
    last={};last_frame={}
    for f in range(n):
        d=details[f] if details and f<len(details) else None
        camG=globals_for(inc['global_orient'][f],inc['body_pose'][f]) if inc else None
        for side, wrist, first in (('left',20,25),('right',21,40)):
            hand=(d or {}).get('hands',{}).get(side)
            if hand:
                last[side]=hand;last_frame[side]=f
            elif f-last_frame.get(side,-1000)<=round(float(params.get('fps',30))*.15):hand=last.get(side)
            if not hand:continue
            points=palm_points(hand['world'],'left')
            if points is None:continue
            sub=lambda a,b:[a[k]-b[k] for k in range(3)]
            rest_basis=frame_from_axes(sub(rest[first+3],rest[wrist]),sub(rest[first],rest[first+6]))
            if camG:
                w=hand['world'];observed=frame_from_axes(sub(w[9],w[0]),sub(w[5],w[17]))
                desired=matmul(observed,transpose(rest_basis))
                local=matmul(transpose(camG[smpl.PARENTS[wrist]]),desired)
                rv=matrix_to_axis_angle(local)
                output['body_pose'][f][3*(wrist-1):3*wrist]=rv
                if 'incam' in output:output['incam']['body_pose'][f][3*(wrist-1):3*wrist]=rv
            pose=[]
            # SMPL-X order: index, middle, pinky, ring, thumb.
            for group,landmark in enumerate((5,9,17,13,1)):
                parent_rotation=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
                for k in range(3):
                    j=first+group*3+k
                    rest_direction=sub(rest[j+1],rest[j]) if k<2 else sub(rest[j],rest[j-1])
                    desired=mat_vec(rest_basis,sub(points[landmark+k+1],points[landmark+k]))
                    local_direction=mat_vec(transpose(parent_rotation),desired)
                    rotation=swing(rest_direction,local_direction)
                    pose.extend(matrix_to_axis_angle(rotation));parent_rotation=matmul(parent_rotation,rotation)
            output[side+'_hand_pose'][f]=pose
    return output


def to_bvh(params,rest,parents,end_offsets):
    joints=[Joint(name,(0.,0.,0.)) for name in NAMES]
    for i,p in enumerate(parents):
        if p<0:continue
        joints[i].offset=tuple((rest[i][k]-rest[p][k])*100 for k in range(3));joints[p].children.append(joints[i])
    for i,joint in enumerate(joints):
        if not joint.children:joint.end_offset=tuple(v*100 for v in end_offsets.get(joint.name,[0,0,.02]))
    frames=[];previous={}
    flip=((1.,0.,0.),(0.,-1.,0.),(0.,0.,-1.)) if params.get('cam_to_yup') else None
    for f in range(len(params['transl'])):
        vectors=[params['global_orient'][f]]+[params['body_pose'][f][i*3:i*3+3] for i in range(21)]
        vectors.extend(params.get(key,[[0.]*size]*len(params['transl']))[f][i:i+3]
            for key,size in (('jaw_pose',3),('leye_pose',3),('reye_pose',3),('left_hand_pose',45),('right_hand_pose',45))
            for i in range(0,size,3))
        frame={}
        for i,(name,rv) in enumerate(zip(NAMES,vectors)):
            rotation=axis_angle_to_matrix(rv)
            if i==0 and flip:rotation=matmul(flip,rotation)
            e=continuous_euler(matrix_to_euler_zxy(rotation),previous.get(name));previous[name]=e;frame[name]={'rot':e}
        position=[rest[0][k]+params['transl'][f][k] for k in range(3)]
        if flip:position=mat_vec(flip,position)
        frame['Hips']['pos']=tuple(p*100 for p in position);frames.append(frame)
    return joints[0],frames
