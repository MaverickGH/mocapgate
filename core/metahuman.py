"""Experimental MediaPipe-to-MetaHuman Faceboard curves; no character assets."""
import math


def profile():
    """Initial semantic mapping, requiring calibration on the actual character."""
    mapping = {
        'CTRL_C_jaw.translateY': {'jawOpen': 1},
        'CTRL_C_jaw.translateX': {'jawRight': 1, 'jawLeft': -1},
        'CTRL_C_jaw_fwdBack.translateY': {'jawForward': 1},
        'CTRL_C_mouth.translateX': {'mouthRight': 1, 'mouthLeft': -1},
    }
    pairs = {
        'brow_raiseIn': {'browInnerUp': 1},
        'brow_raiseOut': {'browOuterUp': 1},
        'brow_down': {'browDown': 1},
        'eye_blink': {'eyeBlink': 1, 'eyeWide': -1},
        'eye_squintInner': {'eyeSquint': 1},
        'eye_cheekRaise': {'cheekSquint': 1},
        'mouth_cornerPull': {'mouthSmile': 1},
        'mouth_cornerDepress': {'mouthFrown': 1},
        'mouth_dimple': {'mouthDimple': 1},
        'mouth_stretch': {'mouthStretch': 1},
        'mouth_upperLipRaise': {'mouthUpperUp': 1},
        'mouth_lowerLipDepress': {'mouthLowerDown': 1},
    }
    for side, suffix in (('L', 'Left'), ('R', 'Right')):
        for control, sources in pairs.items():
            mapping[f'CTRL_{side}_{control}.translateY'] = {
                name if name == 'browInnerUp' else name + suffix: weight
                for name, weight in sources.items()
            }
    return mapping


def faceboard_ranges(board):
    ranges = {}
    for control in board['gui']['controls']:
        for axis in control.get('axes', []):
            for dest in axis.get('destinations', []):
                if dest['dst_min'] != dest['dst_max']:
                    ranges[dest['target']] = (dest['dst_min'], dest['dst_max'])
    return ranges


def export_curves(capture, board, mapping=None):
    mapping = profile() if mapping is None else mapping
    if not mapping:
        raise ValueError('The MetaHuman mapping has no channels')
    ranges = faceboard_ranges(board)
    missing = sorted(set(mapping) - set(ranges))
    if missing:
        raise ValueError('Controls absent from this Faceboard: ' + ', '.join(missing))
    fps = float(capture['fps'])
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('Capture fps must be finite and positive')
    frames = []
    observed = set()
    for frame in capture['frames']:
        face = (frame or {}).get('face')
        if not face:
            frames.append(None)
            continue
        coefficients = face['blendshapes']
        observed.update(coefficients)
        values = {}
        for name, sources in mapping.items():
            value = 0.
            for source, weight in sources.items():
                coefficient = float(coefficients.get(source, 0))
                weight = float(weight)
                if not math.isfinite(coefficient) or not math.isfinite(weight):
                    raise ValueError('Non-finite coefficient or mapping weight: ' + source)
                value += min(1., max(0., coefficient)) * weight
            lo, hi = ranges[name]
            values[name] = min(hi, max(lo, value))
        frames.append(values)
    if not any(frame is not None for frame in frames):
        raise ValueError('No detected face in this capture')
    used = {name for sources in mapping.values() for name in sources}
    return {'format': 'mocapgate.metahuman-face/1', 'rig_def': board['rig_def'],
            'mapping_status': 'experimental-needs-character-calibration',
            'fps': fps, 'id': capture.get('id'), 'channels': list(mapping),
            'frames': frames, 'unmapped_observed': sorted(observed - used)}
