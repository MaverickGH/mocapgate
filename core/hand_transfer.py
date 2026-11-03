"""GEM-X (SOMA) wrists and fingers onto a GVHMR (SMPL) skeleton. Stdlib only.

GVHMR keeps the body (and its feet); only the wrist and the 15 finger joints per side are
replaced, relative to the GVHMR forearm.

Rotation transfer, per mapped bone j with mapped parent p (BVH convention: identity rest
orientation, local L such that world delta D[j] = D[p]·L[j]). Each skeleton gets an
anatomical rest frame A per bone, built from its own rest joint positions: x along the bone,
y towards the back of the hand (from the rest palm; thumb: turned out of the palm as in
hand_fit.THUMB_FRAME). The anatomical frame in a pose is D·A,
so the pose of j relative to p is H = A_s[p]ᵀ · L_s[p→j] · A_s[j] (L_s[p→j] — product of the
source locals between p and j, e.g. SOMA's metacarpal joint). On the target the same H gives
L_t[j] = A_t[p] · H · A_t[j]ᵀ — i.e. R_target_world = R_src_world · R_src_rest⁻¹ · R_target_rest
taken relative to the forearm, so different rest poses (A-pose, curled rest fingers, other
thumb rest) cancel out.

Afterwards the result is projected onto the anatomical hand model of core.hand_fit (wrist
limits, finger flexion/abduction limits, no finger twist), sampled in seconds (GEM-X
recognition fps → export fps) and faded in/out where the GEM-X person is missing.
"""
import math
from core import hand_fit
from core.rotations import (axis_angle_to_matrix, matmul, transpose, frame_from_axes, matrix_to_quat,
                            quat_to_matrix, slerp, euler_zxy_to_matrix, matrix_to_euler_zxy, continuous_euler)

SIDES = (('left', 'Left'), ('right', 'Right'))
FINGERS = tuple(f for f, _ in hand_fit.FINGERS)
SMPL = {'left': (18, 20), 'right': (19, 21)}  # forearm (elbow), hand (wrist) in core.smpl order


def soma_map(prefix):
    """[(our joint, our parent, SOMA joints composed from our parent, SOMA joint of the bone, SOMA bone end)].

    SOMA fingers: Thumb1-3 + ThumbEnd (CMC, MCP, IP); Index..Pinky 1-4 + End, where 1 is the
    metacarpal (carpal joint) and 2 the knuckle (MCP). Ours: Thumb1-3 from the CMC, others 1-3
    from the MCP — so SOMA's metacarpal rotation is folded into our first finger joint.
    """
    rows = [(prefix+'Hand', prefix+'ForeArm', (prefix+'Hand',), prefix+'Hand', prefix+'HandMiddle2')]
    for finger in FINGERS:
        base = prefix+'Hand'+finger
        src = [base+'1', base+'2', base+'3', base+'End'] if finger == 'Thumb' else \
              [base+'2', base+'3', base+'4', base+'End']
        parent = prefix+'Hand'
        for k in range(3):
            chain = (base+'1', base+'2') if finger != 'Thumb' and k == 0 else (src[k],)
            rows.append((f'{base}{k+1}', parent, chain, src[k], src[k+1]))
            parent = f'{base}{k+1}'
    return rows


def _sub(a, b): return [a[i]-b[i] for i in range(3)]
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _palm(distal, radial, side):
    """Rest palm axes: (back-of-hand direction, thumb-bone reference) — same construction on both skeletons.

    The thumb's flexion plane is turned out of the palm: as in hand_fit.THUMB_FRAME its reference
    axis is 0.6·dorsal + 0.8·radial, so a thumb hinge on the source stays a hinge on the target."""
    d = _cross(radial, distal) if side == 'left' else _cross(distal, radial)
    n = math.sqrt(sum(c*c for c in d)) or 1e-12; d = [c/n for c in d]
    x = frame_from_axes(distal, d); r = (x[0][2], x[1][2], x[2][2])  # radial ⟂ distal, dorsal
    r = r if sum(r[i]*radial[i] for i in range(3)) >= 0 else tuple(-c for c in r)
    return d, [.6*d[i]+.8*r[i] for i in range(3)]


# ---------------------------------------------------------------- source (GEM-X person)

def extract(motion, names, parents):
    """GEM-X person (mocapgate.soma/2) → compact hand source: rest of the needed joints and
    local rotations (axis-angle) of the composed joints per recognition frame.

    Raises ValueError when the skeleton does not have the SOMA hand joints."""
    index = {n: i for i, n in enumerate(names)}
    rest = motion['rest']; poses = motion['poses']
    used, rest_of = [], {}
    for side, prefix in SIDES:
        above = {}  # our joint → the SOMA joint it ends on
        for name, parent, chain, bone, end in soma_map(prefix):
            for n in (prefix+'ForeArm', bone, end) + chain:
                if n not in index:
                    raise ValueError(f'GEM-X skeleton has no joint {n}')
                rest_of[n] = list(rest[index[n]])
            # the composed chain must hang directly below the SOMA joint of our parent
            expect = above.get(parent, parent)
            for n in chain:
                if parents[index[n]] < 0 or names[parents[index[n]]] != expect:
                    raise ValueError(f'unexpected SOMA hierarchy at {n}')
                expect = n
            above[name] = chain[-1]
            used += [n for n in chain if n not in used]
        rest_of[prefix+'HandIndex2'] = list(rest[index[prefix+'HandIndex2']])
        rest_of[prefix+'HandPinky2'] = list(rest[index[prefix+'HandPinky2']])
    first = int(motion.get('start_frame', 0)); last = int(motion.get('end_frame', len(poses)-1))
    return {'rest': rest_of, 'joints': used, 'start': first, 'end': min(last, len(poses)-1),
            'poses': [[list(poses[f][index[n]]) for n in used] for f in range(len(poses))]}


def source_frames(rest, side, prefix):
    """Anatomical rest frames of the source bones (keys: our joint names and the forearm)."""
    distal = _sub(rest[prefix+'HandMiddle2'], rest[prefix+'Hand'])
    radial = _sub(rest[prefix+'HandIndex2'], rest[prefix+'HandPinky2'])
    dorsal, thumb = _palm(distal, radial, side)
    A = {prefix+'ForeArm': frame_from_axes(_sub(rest[prefix+'Hand'], rest[prefix+'ForeArm']), dorsal)}
    for name, parent, chain, bone, end in soma_map(prefix):
        A[name] = frame_from_axes(_sub(rest[end], rest[bone]), thumb if 'Thumb' in name else dorsal)
    return A


# ---------------------------------------------------------------- target (GVHMR skeleton)

def target_frames(rest_joints, side, prefix):
    """Anatomical rest frames of our bones: SMPL forearm/hand + the hand_fit finger rig."""
    elbow, wrist = (rest_joints[i] for i in SMPL[side])
    rig = {finger: (base, direction) for finger, _, base, direction, _ in hand_fit.rig(side)}
    distal = rig['Middle'][0]
    radial = _sub(rig['Index'][0], rig['Pinky'][0])
    dorsal, thumb = _palm(distal, radial, side)
    A = {prefix+'ForeArm': frame_from_axes(_sub(wrist, elbow), dorsal), prefix+'Hand': frame_from_axes(distal, dorsal)}
    for finger in FINGERS:
        for k in range(3):
            A[f'{prefix}Hand{finger}{k+1}'] = frame_from_axes(rig[finger][1], thumb if finger == 'Thumb' else dorsal)
    return A


def finger_pose(locals_, side):
    """Our 15 finger local rotations (FINGERS order) → 30 clamped (flexion, abduction) angles."""
    pose = []
    for i, finger in enumerate(FINGERS):
        F = hand_fit.FRAMES.get(finger, hand_fit.I3)
        for k in range(3):
            L = locals_[3*i+k]
            if side == 'right':
                L = matmul(hand_fit.MIRROR, matmul(L, hand_fit.MIRROR))
            R = matmul(transpose(F), matmul(L, F))
            d = (R[0][0], R[1][0], R[2][0])
            flex, abd = hand_fit._angles(d, hand_fit.HINGE[(finger, k)])
            lo, hi, alo, ahi = hand_fit.LIMITS[finger][k]
            pose += [min(hi, max(lo, flex)), min(ahi, max(alo, abd))]
    return pose


def transfer_frame(local, A_s, A_t, side, prefix):
    """One recognition frame: {source joint: local matrix} → (wrist local, 15 finger locals) on the target."""
    out = {}
    for name, parent, chain, bone, end in soma_map(prefix):
        L = local[chain[0]]
        for n in chain[1:]:
            L = matmul(L, local[n])
        H = matmul(transpose(A_s[parent]), matmul(L, A_s[name]))
        out[name] = matmul(A_t[parent], matmul(H, transpose(A_t[name])))
    wrist = hand_fit.clamp_wrist(out[prefix+'Hand'], side)
    fingers = hand_fit.pose_rotations(finger_pose([out[f'{prefix}Hand{f}{k+1}'] for f in FINGERS for k in range(3)], side), side)
    return wrist, fingers


# ---------------------------------------------------------------- time

def fade_weights(present, fps, seconds=.25):
    """Per target frame 0…1: ramps in/out over `seconds` where the source person appears/disappears."""
    step = 1./max(1, round(seconds*float(fps or 30)))
    w = 1. if present and present[0] else 0.; out = []
    for p in present:
        w = min(1., w+step) if p else max(0., w-step)
        out.append(w)
    return out


def apply(frames, fps, rest_joints, source, fade=.25, source_fps=None):
    """Blend GEM-X wrists/fingers into BVH frames (in place; joints as made by hand_bvh.add_fingers).

    source — from extract() plus 'fps'. Target frame f is sampled at t = f / fps seconds, i.e.
    recognition frame t·source_fps, interpolated (slerp) between neighbours; outside the GEM-X
    person's start…end the last transferred pose is held while the weight fades to the
    existing (MediaPipe or relaxed) hand. Returns {'frames': n, 'covered': frames with weight 1}.
    """
    sfps = float(source_fps or source['fps'])
    first, last = source['start'], source['end']
    joints = source['joints']
    cache = {}

    def recognised(i):
        if i not in cache:
            local = {n: axis_angle_to_matrix(rv) for n, rv in zip(joints, source['poses'][i])}
            row = {}
            for side, prefix in SIDES:
                wrist, fingers = transfer_frame(local, frames_s[side], frames_t[side], side, prefix)
                row[side] = [matrix_to_quat(wrist)] + [matrix_to_quat(m) for m in fingers]
            cache[i] = row
        return cache[i]

    frames_s = {side: source_frames(source['rest'], side, prefix) for side, prefix in SIDES}
    frames_t = {side: target_frames(rest_joints, side, prefix) for side, prefix in SIDES}
    tol = 1e-6
    samples = [f/float(fps)*sfps for f in range(len(frames))]
    present = [first-tol <= s <= last+tol for s in samples]
    weights = fade_weights(present, fps, fade)
    previous = {}
    covered = 0
    for f, frame in enumerate(frames):
        w = weights[f]
        if w <= 0:
            continue
        covered += w >= 1
        s = min(max(samples[f], first), last)
        a = int(math.floor(s)); b = min(last, a+1); u = s-a
        qa, qb = recognised(a), recognised(b)
        for side, prefix in SIDES:
            names = [prefix+'Hand'] + [f'{prefix}Hand{finger}{k+1}' for finger in FINGERS for k in range(3)]
            for n, name in enumerate(names):
                if name not in frame:
                    continue
                q = slerp(qa[side][n], qb[side][n], u) if u > 1e-9 and b != a else qa[side][n]
                R = quat_to_matrix(q)
                if w < 1:
                    R = hand_fit.blend_rotation(euler_zxy_to_matrix(*frame[name]['rot']), R, w)
                e = continuous_euler(matrix_to_euler_zxy(R), previous.get(name) or frame[name]['rot'])
                previous[name] = e
                frame[name] = {**frame[name], 'rot': e}
    return {'frames': len(frames), 'covered': covered}


# ---------------------------------------------------------------- people

def boxes(points2d, width, height, min_points=3):
    """Per frame 2D joints (pixels) or None → normalised bounding boxes (x0, y0, x1, y1) or None."""
    out = []
    for frame in points2d or []:
        pts = [p for p in (frame or []) if p is not None and all(math.isfinite(v) for v in p[:2])]
        if len(pts) < min_points:
            out.append(None); continue
        xs = [p[0]/width for p in pts]; ys = [p[1]/height for p in pts]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def iou(a, b):
    w = min(a[2], b[2])-max(a[0], b[0]); h = min(a[3], b[3])-max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.
    inter = w*h
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/union if union > 0 else 0.


def match_people(targets, sources, min_iou=.3, min_overlap=.5):
    """Match target people (GVHMR) to source people (GEM-X) by 2D box overlap over time.

    targets/sources: [{'id', 'fps', 'boxes'}]. Frames are compared at the same time in seconds.
    A pair counts when they overlap at least min(min_overlap s, half of the target's visible time)
    with mean IoU ≥ min_iou; pairs are assigned greedily by mean IoU × coverage (one source per
    target). Returns {target id: {'source', 'iou', 'seconds'}}.
    """
    pairs = []
    for t in targets:
        tf = float(t['fps']); visible = sum(b is not None for b in t['boxes'])/tf
        for s in sources:
            sf = float(s['fps']); values = []
            for f, box in enumerate(t['boxes']):
                if box is None:
                    continue
                i = int(round(f/tf*sf))
                if 0 <= i < len(s['boxes']) and s['boxes'][i] is not None:
                    values.append(iou(box, s['boxes'][i]))
            if not values:
                continue
            seconds = len(values)/tf; mean = sum(values)/len(values)
            if mean >= min_iou and seconds >= min(min_overlap, .5*visible):
                pairs.append((mean*min(1., seconds/visible if visible else 0.), mean, seconds, t['id'], s['id']))
    out, used = {}, set()
    for score, mean, seconds, tid, sid in sorted(pairs, key=lambda p: -p[0]):
        if tid in out or sid in used:
            continue
        out[tid] = {'source': sid, 'iou': round(mean, 3), 'seconds': round(seconds, 2)}
        used.add(sid)
    return out
