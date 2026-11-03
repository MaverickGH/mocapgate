"""MoCapGate — мимика (52 коэффициента ARKit от MediaPipe) в кривые для анимации.

Кадры захвата (частота распознавания) → кадры экспорта: линейная интерполяция, пропуски заполняются
между соседними кадрами с лицом, края держат ближайшее значение. Результат — CSV (кадр, время, 52 кривые)
и узел FaceExpressions с ключами в сцене Maya (атрибуты с именами ARKit — подключаются к blendShape).
Только stdlib.
"""
from __future__ import annotations
import re
from pathlib import Path

# MediaPipe's complete model output omits tongueOut. Keep the standard ARKit
# export slot neutral; a zero channel does not mean tongue motion was tracked.
MEDIAPIPE_EXPRESSIONS = frozenset('''browDownLeft browDownRight browInnerUp browOuterUpLeft browOuterUpRight
cheekPuff cheekSquintLeft cheekSquintRight eyeBlinkLeft eyeBlinkRight eyeLookDownLeft eyeLookDownRight
eyeLookInLeft eyeLookInRight eyeLookOutLeft eyeLookOutRight eyeLookUpLeft eyeLookUpRight eyeSquintLeft
eyeSquintRight eyeWideLeft eyeWideRight jawForward jawLeft jawOpen jawRight mouthClose mouthDimpleLeft
mouthDimpleRight mouthFrownLeft mouthFrownRight mouthFunnel mouthLeft mouthLowerDownLeft mouthLowerDownRight
mouthPressLeft mouthPressRight mouthPucker mouthRight mouthRollLower mouthRollUpper mouthShrugLower
mouthShrugUpper mouthSmileLeft mouthSmileRight mouthStretchLeft mouthStretchRight mouthUpperUpLeft
mouthUpperUpRight noseSneerLeft noseSneerRight'''.split())


def curves(details: list, source_fps: float, target_fps: float, frames: int):
    """→ (имена, значения[кадр экспорта][кривая]) или None, если лица нет ни в одном кадре."""
    keyed = [(i, (d or {}).get('face') or {}) for i, d in enumerate(details or [])]
    keyed = [(i, f['blendshapes']) for i, f in keyed if f.get('blendshapes')]
    if not keyed:
        return None
    names = {n for _, b in keyed for n in b if n != '_neutral'}
    if MEDIAPIPE_EXPRESSIONS.issubset(names):
        names.add('tongueOut')
    names = sorted(names)
    times = [i / source_fps for i, _ in keyed]
    out = []
    j = 0
    for k in range(frames):
        t = k / target_fps
        while j + 1 < len(times) and times[j + 1] <= t:
            j += 1
        if t <= times[0]:
            a = b = keyed[0][1]; w = 0.0
        elif j + 1 >= len(times):
            a = b = keyed[-1][1]; w = 0.0
        else:
            a, b = keyed[j][1], keyed[j + 1][1]
            w = (t - times[j]) / (times[j + 1] - times[j])
        out.append([round(float(a.get(n, 0)) * (1 - w) + float(b.get(n, 0)) * w, 5) for n in names])
    return names, out


def write_csv(path, names, values, fps):
    lines = ['frame,time,' + ','.join(names)]
    lines += [f'{k + 1},{k / fps:.5f},' + ','.join(f'{v:.5g}' for v in row) for k, row in enumerate(values)]
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def append_maya(path, names, values, node='FaceExpressions'):
    """Дописывает в .ma узел с атрибутами-кривыми мимики (animCurveTU, кадры с 1, как у суставов)."""
    lines = [f'createNode transform -n "{node}";']
    attrs = [re.sub(r'[^A-Za-z0-9_]', '_', name) for name in names]
    # addAttr в .ma относится к последнему созданному узлу — сначала все атрибуты, потом кривые
    lines += [f'addAttr -ci true -k true -sn "{a}" -ln "{a}" -min 0 -max 1 -at "double";' for a in attrs]
    for index, attr in enumerate(attrs):
        curve = f'{node}_{attr}'
        series = [row[index] for row in values]
        lines += [f'createNode animCurveTU -n "{curve}";', 'setAttr ".tan" 2;',
                  f'setAttr -s {len(series)} ".ktv[0:{len(series) - 1}]" '
                  + ' '.join(f'{i + 1} {v:.6g}' for i, v in enumerate(series)) + ';',
                  f'connectAttr "{curve}.o" "{node}.{attr}";']
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')


def export(take, stem, details, source_fps, target_fps, frames):
    """CSV рядом с BVH и узел в сцене Maya. → имя CSV или None."""
    result = curves(details, source_fps, target_fps, frames)
    if not result:
        return None
    names, values = result
    write_csv(Path(take) / f'{stem}.face.csv', names, values, target_fps)
    scene = Path(take) / f'{stem}.ma'
    if scene.is_file():
        append_maya(scene, names, values)
    return f'{stem}.face.csv'


def append_csv_to_maya(csv_path, scene):
    """Та же мимика в другую сцену Maya (персонаж Man_Rig) — из готового CSV."""
    rows = Path(csv_path).read_text(encoding='utf-8').splitlines()
    names = rows[0].split(',')[2:]
    values = [[float(v) for v in row.split(',')[2:]] for row in rows[1:] if row]
    if names and values and Path(scene).is_file():
        append_maya(scene, names, values)
