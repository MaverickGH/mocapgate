"""Anatomical hand fit for MediaPipe hand world landmarks (stdlib only).

Canonical hand frame (left hand; right hands are mirrored in x):
x — distal (wrist → middle MCP), y — dorsal (back of the hand), z — radial (thumb side).
This is the SMPL T-pose hand: palm down, thumb forward, so the finger rig agrees with the
body's wrist rotation. Each joint is flexion (palmar positive) + abduction (radial positive)
with zero twist, clamped to anatomical ranges.

MediaPipe world landmarks are metric with image-aligned axes (x right, y down, z away from
the camera; the ROI rotation is undone only in the image plane), i.e. OpenCV camera axes.
GVHMR "incam" parameters live in the same OpenCV camera space, so the observed palm and the
forearm from forward kinematics can be compared directly.
"""
import math
from core.rotations import (axis_angle_to_matrix, matmul, transpose, mat_vec, frame_from_axes, swing,
                            slerp, matrix_to_quat, quat_to_matrix)

FINGERS = (('Thumb', 1), ('Index', 5), ('Middle', 9), ('Ring', 13), ('Pinky', 17))
I3 = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
MIRROR = ((-1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
FLIP_YUP = ((1., 0., 0.), (0., -1., 0.), (0., 0., -1.))


def _sub(a, b): return [a[i]-b[i] for i in range(3)]
def _dot(a, b): return sum(a[i]*b[i] for i in range(3))
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _len(v): return math.sqrt(_dot(v, v))
def _norm(v):
    n = _len(v) or 1e-12
    return tuple(c/n for c in v)
def _rot(axis, deg): return axis_angle_to_matrix([c*math.radians(deg) for c in axis])
def _clamp(v, lo, hi): return max(lo, min(hi, v))
def _smooth(u):
    u = _clamp(u, 0., 1.)
    return u*u*(3-2*u)


# Thumb metacarpal rest: distal, radial and slightly palmar; it flexes toward palm and ulnar side.
THUMB_DIR = _norm((0.70, -0.30, 0.65))
_f = (0., -0.6, -0.8); _f = _norm([_f[i]-_dot(_f, THUMB_DIR)*THUMB_DIR[i] for i in range(3)])
_ty = tuple(-c for c in _f)
THUMB_FRAME = tuple(tuple((THUMB_DIR, _ty, _cross(THUMB_DIR, _ty))[c][r] for c in range(3)) for r in range(3))
FRAMES = {'Thumb': THUMB_FRAME}

# (flex min, flex max, abduction min, abduction max), degrees, per joint 1..3.
_FINGER_LIMITS = ((-20., 90., -20., 20.), (0., 110., 0., 0.), (0., 80., 0., 0.))
LIMITS = {'Thumb': ((-25., 55., -30., 45.), (-5., 60., -10., 10.), (-5., 80., 0., 0.)),
          'Index': _FINGER_LIMITS, 'Middle': _FINGER_LIMITS, 'Ring': _FINGER_LIMITS, 'Pinky': _FINGER_LIMITS}
HINGE = {(f, k): k == 2 if f == 'Thumb' else k > 0 for f, _ in FINGERS for k in range(3)}
# Relaxed hand: a gentle curl that increases toward the little finger.
NEUTRAL = (10., 15., 10., 0., 8., 0.,
           10., 0., 20., 0., 10., 0.,
           14., 0., 24., 0., 12., 0.,
           18., 0., 28., 0., 14., 0.,
           22., -3., 32., 0., 16., 0.)
# Wrist relative to forearm: flexion/extension ±80, radial 20 / ulnar 35, twist (pronation) ±90.
WRIST_LIMITS = (-80., 80., -35., 20., -90., 90.)

BASE = {'Thumb': (.025, -.01, .025), 'Index': (.065, 0., .025), 'Middle': (.065, 0., 0.),
        'Ring': (.062, 0., -.02), 'Pinky': (.058, 0., -.04)}
LENGTHS = {'Thumb': (.032, .025, .022)}
DEFAULT_LENGTHS = (.035, .025, .02)


def rig(side):
    """[(finger, landmark start, base offset m, unit bone direction, lengths)] in body rest axes."""
    s = 1. if side == 'left' else -1.
    out = []
    for finger, start in FINGERS:
        b = BASE[finger]; d = THUMB_DIR if finger == 'Thumb' else (1., 0., 0.)
        out.append((finger, start, (s*b[0], b[1], b[2]), (s*d[0], d[1], d[2]), LENGTHS.get(finger, DEFAULT_LENGTHS)))
    return out


def _q(flex, abd):
    return matmul(_rot((0., 1., 0.), -abd), _rot((0., 0., 1.), -flex))


def _angles(d, hinge):
    if hinge:
        return math.degrees(math.atan2(-d[1], d[0])), 0.
    abd = math.atan2(d[2], d[0]) if d[0] >= 0 else math.atan2(-d[2], -d[0])
    if math.hypot(d[0], d[2]) < .15:
        abd = 0.
    u = mat_vec(_rot((0., 1., 0.), math.degrees(abd)), d)  # abduction removed: bone in the flexion plane
    return math.degrees(math.atan2(-u[1], u[0])), math.degrees(abd)


def canonical_points(world, side):
    """21 points in the canonical (left) hand frame and palm length, or None if degenerate."""
    pts = [[(-p[0] if side == 'right' else p[0]), p[1], p[2]] for p in world]
    o = pts[0]; D = _sub(pts[9], o); R = _sub(pts[5], pts[17])
    if _len(D) < .01 or _len(R) < .01:
        return None
    x = _norm(D); z = _norm([R[i]-_dot(R, x)*x[i] for i in range(3)]); y = _cross(z, x)
    return [(_dot(q, x), _dot(q, y), _dot(q, z)) for q in (_sub(p, o) for p in pts)], _len(D)


def is_flipped(points, size):
    """Mirror-image hand (wrong chirality / depth flip): fingertips far on the dorsal side."""
    lift = [points[s+3][1]-points[s][1] for f, s in FINGERS if f != 'Thumb']
    return sum(lift)/len(lift) > .25*size


def solve(points):
    """Canonical points → 30 clamped angles (flex, abd per joint, FINGERS order)."""
    pose = []
    for finger, s in FINGERS:
        F = FRAMES.get(finger, I3); P = I3
        for k in range(3):
            b = _sub(points[s+k+1], points[s+k])
            d = mat_vec(transpose(F), mat_vec(transpose(P), b)) if _len(b) > 1e-6 else (1., 0., 0.)
            flex, abd = _angles(_norm(d), HINGE[(finger, k)])
            lo, hi, alo, ahi = LIMITS[finger][k]
            flex = _clamp(flex, lo, hi); abd = _clamp(abd, alo, ahi)
            pose += [flex, abd]
            P = matmul(P, matmul(F, matmul(_q(flex, abd), transpose(F))))
    return pose


def fit(world, side):
    """MediaPipe world landmarks → (pose, palm length, flipped) or None."""
    c = canonical_points(world, side)
    if c is None:
        return None
    points, size = c
    flipped = is_flipped(points, size)
    if flipped:
        points = [(p[0], -p[1], p[2]) for p in points]
    return solve(points), size, flipped


def pose_rotations(pose, side):
    """Local joint rotations (15, FINGERS order) in body rest axes for the side."""
    out = []
    for i, (finger, _) in enumerate(FINGERS):
        F = FRAMES.get(finger, I3)
        for k in range(3):
            j = 2*(3*i+k)
            R = matmul(F, matmul(_q(pose[j], pose[j+1]), transpose(F)))
            out.append(matmul(MIRROR, matmul(R, MIRROR)) if side == 'right' else R)
    return out


def landmarks(pose, side, orientation=I3, origin=(0., 0., 0.)):
    """Synthetic MediaPipe-like world landmarks for a pose; orientation = hand rotation in camera."""
    pts = [None]*21; pts[0] = (0., 0., 0.)
    rots = pose_rotations(pose, side)
    for i, (finger, start, base, direction, lengths) in enumerate(rig(side)):
        p = base; pts[start] = p; G = I3
        for k in range(3):
            G = matmul(G, rots[3*i+k])
            p = tuple(p[c]+lengths[k]*v for c, v in enumerate(mat_vec(G, direction)))
            pts[start+k+1] = p
    return [[mat_vec(orientation, q)[c]+origin[c] for c in range(3)] for q in pts]


# ---------------------------------------------------------------- wrist

def decompose_wrist(L, side):
    """Local wrist rotation → (flexion, radial deviation, twist) degrees in the canonical frame."""
    Lc = matmul(MIRROR, matmul(L, MIRROR)) if side == 'right' else L
    d = (Lc[0][0], Lc[1][0], Lc[2][0])
    flex, dev = _angles(d, False)
    T = matmul(transpose(_q(flex, dev)), Lc)
    return flex, dev, math.degrees(math.atan2(T[2][1], T[1][1]))


def compose_wrist(flex, dev, twist, side):
    Lc = matmul(_q(flex, dev), _rot((1., 0., 0.), twist))
    return matmul(MIRROR, matmul(Lc, MIRROR)) if side == 'right' else Lc


def clamp_wrist(L, side):
    flex, dev, twist = decompose_wrist(L, side)
    a, b, c, d, e, f = WRIST_LIMITS
    return compose_wrist(_clamp(flex, a, b), _clamp(dev, c, d), _clamp(twist, e, f), side)


def hand_rotation_camera(world, side, image=None, K=None):
    """Hand (wrist joint) global rotation in OpenCV camera space from the palm landmarks.

    With K and the wrist pixel, the crop's viewing ray is accounted for: the landmark model
    sees an off-centre hand as if the camera looked along that ray.
    """
    Fc = frame_from_axes(_sub(world[9], world[0]), _sub(world[5], world[17]))
    if K and image:
        u, v = image[0][0], image[0][1]
        ray = ((u-K[0][2])/K[0][0], (v-K[1][2])/K[1][1], 1.)
        Fc = matmul(swing((0., 0., 1.), ray), Fc)
    Fr = frame_from_axes(((1. if side == 'left' else -1.), 0., 0.), (0., 0., 1.))
    return matmul(Fc, transpose(Fr))


def forearm_rotations(params):
    """Per frame {'left': G, 'right': G} — forearm global rotations in OpenCV camera space, or None."""
    if not params:
        return None
    pre = None
    if params.get('cam_to_yup'):
        inc = params
    elif params.get('incam'):
        inc = params['incam']
    elif params.get('camera'):
        inc, pre = params, FLIP_YUP  # MediaPipe body: y-up camera → OpenCV (as in pipeline.write_person)
    else:
        return None
    from core.smpl import PARENTS
    out = []
    for g, b in zip(inc.get('global_orient') or [], inc.get('body_pose') or []):
        G = [None]*20
        for i in range(20):
            R = axis_angle_to_matrix(g if i == 0 else b[3*(i-1):3*i])
            G[i] = (matmul(pre, R) if pre else R) if i == 0 else matmul(G[PARENTS[i]], R)
        out.append({'left': G[18], 'right': G[19]})
    return out


def blend_rotation(a, b, w):
    if w <= 0: return a
    if w >= 1: return b
    return quat_to_matrix(slerp(matrix_to_quat(a), matrix_to_quat(b), w))


# ---------------------------------------------------------------- temporal robustness

def _jump(a, b):
    return max(abs(x-y) for x, y in zip(a, b))


def _lerp(a, b, u):
    return [x+(y-x)*u for x, y in zip(a, b)]


def track(raw, fps, neutral=NEUTRAL):
    """Accept/reject per-frame fits and fill gaps.

    raw[f] = None or {'pose', 'size', 'score'}. Rejects low handedness score, implausible or
    sudden palm-size changes and single-frame angular jumps that are not sustained. Short gaps
    are interpolated; long gaps hold briefly, then ease to the relaxed neutral; re-acquisition
    eases back in. Returns (poses, accepted flags).
    """
    n = len(raw); fps = float(fps) or 30.
    hold = max(1, round(.1*fps)); fade = max(2, round(.3*fps)); bridge = max(1, round(.4*fps))
    blend = max(2, round(.2*fps)); sustain = max(2, round(.1*fps)); thr = max(35., 2250./fps)
    ok = [False]*n; window = []; last = None; last_f = -10**9

    def plausible(e):
        return e and e.get('score', 1.) >= .55 and .03 < e['size'] < .2

    for f, e in enumerate(raw):
        if not plausible(e):
            continue
        median = sorted(window)[len(window)//2] if len(window) >= 3 else None
        window = (window + [e['size']])[-15:]
        if median and not .75 <= e['size']/median <= 1.33:
            continue
        if last is not None and f-last_f <= bridge and _jump(e['pose'], last) > thr:
            ahead = [raw[f+j] if f+j < n else None for j in range(1, sustain+1)]
            if not all(plausible(a) and _jump(a['pose'], e['pose']) <= thr for a in ahead):
                continue
        ok[f] = True; last = e['pose']; last_f = f

    out = [list(neutral) for _ in range(n)]
    goods = [f for f in range(n) if ok[f]]
    for f in goods:
        out[f] = list(raw[f]['pose'])
    starts = [goods[0]] if goods else []
    for a, b in zip(goods, goods[1:] + [None]):
        end = b if b is not None else n
        gap = end-a-1
        if gap <= 0:
            continue
        if b is not None and gap <= bridge:
            for f in range(a+1, b):
                out[f] = _lerp(out[a], out[b], (f-a)/(b-a))
            continue
        for f in range(a+1, end):
            t = f-a
            out[f] = list(out[a]) if t <= hold else _lerp(out[a], neutral, _smooth((t-hold)/fade))
        if b is not None:
            starts.append(b)
    for b in starts:
        anchor = list(out[b-1]) if b > 0 else list(neutral)
        for j in range(blend):
            f = b+j
            if f >= n or not ok[f]:
                break
            out[f] = _lerp(anchor, out[f], _smooth((j+1)/(blend+1)))
    return out, ok


def wrist_weights(raw, ok, fps, maximum=.9):
    """Confidence of the hand-based wrist correction, ramped so the wrist never pops."""
    step = 1./max(1, round(.2*float(fps or 30)))
    w = 0.; out = []
    for e, good in zip(raw, ok):
        target = 0.
        if good:
            target = maximum*_clamp((e.get('score', 1.)-.5)/.35, 0., 1.)*(.3 if e.get('flipped') else 1.)
        w = min(target, w+step) if target > w else max(target, w-step)
        out.append(w)
    return out
