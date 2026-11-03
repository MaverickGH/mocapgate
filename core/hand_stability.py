"""Bound local wrist/finger outliers on SO(3), without clamping Euler channels."""
import math
from core.rotations import euler_zxy_to_matrix, matrix_to_axis_angle, axis_angle_to_matrix, matrix_to_euler_zxy, continuous_euler, matmul, transpose
from core.video_timing import rotation


# One-Euro on SO(3): (min cutoff Hz, speed gain Hz per deg/s, max cutoff Hz). Fingers are noisier
# than wrists, so they rest at a lower cutoff; fast motion raises the cutoff and stays responsive.
WRIST_FILTER = (3.0, .02, 12.0)
FINGER_FILTER = (1.6, .02, 10.0)
SPEED_CUTOFF = 1.0


def _alpha(cutoff, fps):
    return 1 - math.exp(-2 * math.pi * cutoff / fps)


def _angle_between(a, b):
    """Geodesic angle (degrees) between two rotation vectors."""
    d = matrix_to_axis_angle(matmul(transpose(axis_angle_to_matrix(a)), axis_angle_to_matrix(b)))
    return math.degrees(math.sqrt(sum(v*v for v in d)))


def stabilize(frames, fps):
    previous = {}; eulers = {}; speeds = {}
    for frame in frames:
        for name, data in frame.items():
            plain = name.split(':')[-1]
            if not (plain in ('LeftHand','RightHand') or plain.startswith(('LeftHand','RightHand'))):
                continue
            rv = matrix_to_axis_angle(euler_zxy_to_matrix(*data['rot']))
            angle = math.sqrt(sum(v*v for v in rv))
            wrist = plain in ('LeftHand','RightHand')
            limit = math.radians(160 if wrist else 150)
            if angle > limit:
                rv = [v * limit/angle for v in rv]
            if name in previous:
                low, gain, high = WRIST_FILTER if wrist else FINGER_FILTER
                speed = _angle_between(previous[name], rv) * fps
                speeds[name] = speeds.get(name, speed) + _alpha(SPEED_CUTOFF, fps) * (speed - speeds.get(name, speed))
                rv = rotation(previous[name], rv, _alpha(min(high, low + gain * speeds[name]), fps))
            previous[name] = rv
            angles = continuous_euler(matrix_to_euler_zxy(axis_angle_to_matrix(rv)), eulers.get(name))
            data['rot'] = angles; eulers[name] = angles
    return frames


def stabilize_params(params, fps):
    """Filter before skinning, so the mesh and exported skeleton agree."""
    def series(rows, indices, limit):
        alpha = 1 - math.exp(-2 * math.pi * 8 / fps)
        prev = {}
        for row in rows:
            for index in indices:
                rv = matrix_to_axis_angle(axis_angle_to_matrix(row[index:index+3]))
                angle = math.sqrt(sum(v*v for v in rv))
                if angle > math.radians(limit):
                    rv = [v*math.radians(limit)/angle for v in rv]
                if index in prev:
                    rv = rotation(prev[index], rv, alpha)
                prev[index] = rv
                row[index:index+3] = rv
    series(params['body_pose'], (57,60), 160)
    for key in ('left_hand_pose','right_hand_pose'):
        if key in params: series(params[key], range(0,45,3), 150)
    if params.get('incam'): stabilize_params(params['incam'], fps)
    return params
