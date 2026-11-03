"""Finger articulation and hand-corrected wrists in the body's wrist frame.

Fingers come from MediaPipe hand world landmarks through an anatomical model
(core.hand_fit): flexion/abduction per joint, clamped, no twist, no hyperextension.
Outlier frames are rejected, gaps ease to a relaxed curl. When the body's camera-space
pose is known (params with incam / cam_to_yup / camera), a visible palm also corrects the
wrist relative to the forearm, blended by confidence. Wrists are always clamped to
anatomical ranges. No inferred toes.
"""
import math
from core.skeleton import Joint
from core.rotations import (frame_from_axes, transpose, mat_vec, matmul, matrix_to_euler_zxy, euler_zxy_to_matrix,
                            continuous_euler)
from core import hand_fit

FINGERS = hand_fit.FINGERS
IDENTITY = ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def palm_points(world, side):
    def sub(a,b): return [a[k]-b[k] for k in range(3)]
    axis = sub(world[9], world[0]); spread = sub(world[5], world[17])
    if math.dist(world[9], world[0]) < .01 or math.dist(world[5], world[17]) < .01:
        return None
    basis = transpose(frame_from_axes(axis, spread))
    sign = 1 if side == 'left' else -1
    return [[sign*q[0], q[1], sign*q[2]] for p in world for q in [mat_vec(basis, sub(p,world[0]))]]


def add_fingers(root, frames, details, fps, params=None):
    """params (optional): SMPL parameters of the person; enables wrist correction from the palm."""
    joints = {}
    def walk(j):
        joints[j.name] = j
        for c in j.children: walk(c)
    walk(root)
    forearms = hand_fit.forearm_rotations(params) if params else None
    K = (params or {}).get('K')
    for side, prefix in (('left','Left'), ('right','Right')):
        wrist = joints[prefix+'Hand']; wrist.end_offset = None
        chains = []
        for finger, start, base, direction, lengths in hand_fit.rig(side):
            # Stable adult-sized rest rig (SMPL T-pose hand: palm down, thumb forward).
            chain = []; parent = wrist
            for k in range(3):
                offset = base if k == 0 else tuple(v*lengths[k-1] for v in direction)
                child = Joint(f'{prefix}Hand{finger}{k+1}', tuple(v*100 for v in offset))
                parent.children.append(child); parent = child; chain.append(child)
            parent.end_offset = tuple(v*lengths[2]*100 for v in direction)
            chains.append(chain)
        raw = []
        for f in range(len(frames)):
            d = details[f] if f < len(details) else None
            hand = (d or {}).get('hands', {}).get(side)
            result = hand_fit.fit(hand['world'], side) if hand and hand.get('world') else None
            raw.append({'pose': result[0], 'size': result[1], 'flipped': result[2], 'score': hand.get('score', 1.),
                        'hand': hand} if result else None)
        poses, ok = hand_fit.track(raw, fps)
        weights = hand_fit.wrist_weights(raw, ok, fps)
        previous = {}; desired = None
        for f, frame in enumerate(frames):
            data = frame.get(prefix+'Hand')
            if data is not None:
                local = euler_zxy_to_matrix(*data['rot'])
                if forearms and f < len(forearms):
                    if ok[f]:
                        hand = raw[f]['hand']
                        G = hand_fit.hand_rotation_camera(hand['world'], side, hand.get('image'), K)
                        desired = matmul(transpose(forearms[f][side]), G)
                    if desired is not None and weights[f] > 0:
                        local = hand_fit.blend_rotation(local, desired, weights[f])
                local = hand_fit.clamp_wrist(local, side)
                e = continuous_euler(matrix_to_euler_zxy(local), previous.get(wrist.name))
                previous[wrist.name] = e; data['rot'] = e
            for chain, rotations in zip(chains, _chunks(hand_fit.pose_rotations(poses[f], side), 3)):
                for joint, rotation in zip(chain, rotations):
                    e = continuous_euler(matrix_to_euler_zxy(rotation), previous.get(joint.name))
                    previous[joint.name] = e; frame[joint.name] = {'rot': e}
    return root, frames


def _chunks(items, size):
    return [items[i:i+size] for i in range(0, len(items), size)]
