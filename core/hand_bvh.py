"""Approximate finger articulation in the body's wrist frame.

Hand world points are palm-centred metres. Palm orientation is removed before
retargeting so camera/world orientation does not leak into local finger angles.
Wrist orientation remains supplied by the body tracker. No inferred toes.
"""
import math
from core.skeleton import Joint
from core.rotations import frame_from_axes, transpose, mat_vec, swing, matmul, matrix_to_euler_zxy, continuous_euler

FINGERS = (('Thumb', 1), ('Index', 5), ('Middle', 9), ('Ring', 13), ('Pinky', 17))
IDENTITY = ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def palm_points(world, side):
    def sub(a,b): return [a[k]-b[k] for k in range(3)]
    axis = sub(world[9], world[0]); spread = sub(world[5], world[17])
    if math.dist(world[9], world[0]) < .01 or math.dist(world[5], world[17]) < .01:
        return None
    basis = transpose(frame_from_axes(axis, spread))
    sign = 1 if side == 'left' else -1
    return [[sign*q[0], q[1], sign*q[2]] for p in world for q in [mat_vec(basis, sub(p,world[0]))]]


def add_fingers(root, frames, details, fps):
    joints = {}
    def walk(j):
        joints[j.name] = j
        for c in j.children: walk(c)
    walk(root)
    for side, prefix in (('left','Left'), ('right','Right')):
        wrist = joints[prefix+'Hand']; wrist.end_offset = None
        sign = 1 if side == 'left' else -1
        chains = []
        for index, (finger, start) in enumerate(FINGERS):
            # Stable adult-sized rest rig; observed motion changes rotations, not bone lengths.
            base = (sign*(.025 if finger=='Thumb' else .065), (.035,.025,0.,-.02,-.04)[index], 0.)
            lengths = (.032,.025,.022) if finger=='Thumb' else (.035,.025,.02)
            chain = []; parent = wrist
            for k in range(3):
                name = f'{prefix}Hand{finger}{k+1}'
                offset = base if k==0 else (sign*lengths[k-1],0.,0.)
                child = Joint(name, tuple(v*100 for v in offset))
                parent.children.append(child); parent = child; chain.append(child)
            parent.end_offset = (sign*lengths[2]*100,0.,0.)
            chains.append((start,chain))
        previous = {}; last = None; last_frame = -1000
        for f, frame in enumerate(frames):
            d = details[f] if f < len(details) else None
            hand = (d or {}).get('hands',{}).get(side)
            points = palm_points(hand['world'],side) if hand else None
            if points:
                last, last_frame = points, f
            elif f-last_frame <= round(fps*.15):
                points = last
            for start, chain in chains:
                parent_rotation = IDENTITY
                for k,joint in enumerate(chain):
                    rest = (sign,0.,0.)
                    if points:
                        a,b = points[start+k],points[start+k+1]
                        direction = mat_vec(transpose(parent_rotation),[b[i]-a[i] for i in range(3)])
                        rotation = swing(rest,direction)
                    else:
                        rotation = IDENTITY
                    parent_rotation = matmul(parent_rotation,rotation)
                    e = continuous_euler(matrix_to_euler_zxy(rotation),previous.get(joint.name))
                    previous[joint.name] = e; frame[joint.name] = {'rot':e}
    return root, frames
