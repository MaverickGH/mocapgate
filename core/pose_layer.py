"""MoCapGate — аддитивный слой правки позы поверх движения (stdlib, без numpy).

Ключ слоя (JSON): {"joint": str, "frame": int (с 0), "rot": [x, y, z] градусы, "falloff": int ≥ 0}.
Дельта ключа D = Rx(x)·Ry(y)·Rz(z) (intrinsic XYZ, как THREE.Euler(x, y, z, 'XYZ')),
применяется в ЛОКАЛЬНОМ пространстве сустава справа: R' = R · D
(как bone.quaternion.multiply(dq) в three.js). Точная формула — в JS_SPEC ниже.
"""
from __future__ import annotations
import bisect
import math

from core.rotations import continuous_euler, euler_zxy_to_matrix, matmul, matrix_to_euler_zxy, quat_to_matrix, slerp

JS_SPEC = """
Формула слоя (для порта в JS; кватернионы (w, x, y, z), углы в градусах).

1. Дельта ключа: D = quat(Rx(x)·Ry(y)·Rz(z)) = qx·qy·qz, где
   qx = (cos(x/2), sin(x/2), 0, 0), qy = (cos(y/2), 0, sin(y/2), 0), qz = (cos(z/2), 0, 0, sin(z/2)).
   В three.js: new THREE.Quaternion().setFromEuler(new THREE.Euler(x*DEG, y*DEG, z*DEG, 'XYZ')).

2. Ключи одного сустава сортируются по кадру; при нескольких ключах на одном кадре
   побеждает последний в исходном списке.

3. smoothstep(s) = s*s*(3 - 2*s).
   slerp(a, b, t): если dot(a, b) < 0, b = -b (кратчайшая дуга); если dot > 0.9995 —
   линейная интерполяция компонент; иначе стандартная формула sin; результат нормируется.
   (Это THREE.Quaternion.slerpQuaternions с той же проверкой знака.)

4. Значение слоя L(f) для сустава с ключами k0..kN (кадры f0 < ... < fN):
   - f == fi                    → Di
   - fi < f < f(i+1)            → slerp(Di, D(i+1), smoothstep((f - fi) / (f(i+1) - fi)))
   - f < f0:  d = f0 - f, F = falloff(k0); если F == 0 или d >= F → identity,
              иначе slerp(identity, D0, smoothstep(1 - d / F))
   - f > fN:  d = f - fN, F = falloff(kN); если F == 0 или d >= F → identity,
              иначе slerp(identity, DN, smoothstep(1 - d / F))
   falloff учитывается только у крайних ключей (между ключами всегда интерполяция).

5. Применение: R' = R · L(f), т.е. bone.quaternion.copy(base).multiply(L(f)).
   Кадры, где L(f) — identity (нет ключей, вне falloff или ровно нулевая дельта), не меняются.
"""

_ID = (1.0, 0.0, 0.0, 0.0)


def _smoothstep(s: float) -> float:
    return s * s * (3.0 - 2.0 * s)


def key_quat(rot) -> tuple[float, float, float, float]:
    """[x, y, z] градусы → кватернион (w, x, y, z) для Rx(x)·Ry(y)·Rz(z) = qx·qy·qz."""
    hx, hy, hz = (math.radians(float(a)) / 2 for a in rot)
    cx, sx, cy, sy, cz, sz = math.cos(hx), math.sin(hx), math.cos(hy), math.sin(hy), math.cos(hz), math.sin(hz)
    # qx·qy = (cx·cy, sx·cy, cx·sy, sx·sy); затем ·qz
    w, x, y, z = cx * cy, sx * cy, cx * sy, sx * sy
    return (w * cz - z * sz, x * cz + y * sz, y * cz - x * sz, z * cz + w * sz)


def _num(v, what):
    if isinstance(v, bool):
        raise ValueError(f"{what}: нужно число")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: нужно число") from None
    if not math.isfinite(f):
        raise ValueError(f"{what}: нужно конечное число")
    return f


def _int(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v):
        raise ValueError(f"{what}: нужно целое число")
    return int(v)


def _normalize(keys):
    """Проверить ключи → {сустав: [(кадр, D, falloff), ...] по возрастанию кадра, без дублей}."""
    if keys is None:
        return {}
    if not isinstance(keys, (list, tuple)):
        raise ValueError("Слой: нужен список ключей")
    by_joint: dict[str, dict[int, tuple]] = {}
    for i, k in enumerate(keys):
        where = f"Ключ {i + 1}"
        if not isinstance(k, dict):
            raise ValueError(f"{where}: нужен объект с полями joint, frame, rot, falloff")
        joint = k.get("joint")
        if not isinstance(joint, str) or not joint:
            raise ValueError(f"{where}: не указан сустав (joint)")
        frame = _int(k.get("frame"), f"{where}, кадр")
        if frame < 0:
            raise ValueError(f"{where}: кадр не может быть отрицательным")
        rot = k.get("rot")
        if not isinstance(rot, (list, tuple)) or len(rot) != 3:
            raise ValueError(f"{where}: rot — три угла [x, y, z] в градусах")
        rot = [_num(a, f"{where}, угол") for a in rot]
        falloff = _int(k.get("falloff", 0), f"{where}, затухание")
        if falloff < 0:
            raise ValueError(f"{where}: затухание не может быть отрицательным")
        by_joint.setdefault(joint, {})[frame] = (frame, key_quat(rot), falloff)  # последний побеждает
    return {j: [d[f] for f in sorted(d)] for j, d in by_joint.items()}


def _eval(track, frames_idx, f):
    """Значение слоя на кадре f для отсортированных ключей сустава; None = identity."""
    if not track:
        return None
    i = bisect.bisect_left(frames_idx, f)
    if i < len(track) and frames_idx[i] == f:
        return track[i][1]
    if i == 0:
        f0, d0, F = track[0]
        d = f0 - f
        return None if F == 0 or d >= F else slerp(_ID, d0, _smoothstep(1.0 - d / F))
    if i == len(track):
        fn, dn, F = track[-1]
        d = f - fn
        return None if F == 0 or d >= F else slerp(_ID, dn, _smoothstep(1.0 - d / F))
    fa, da, _ = track[i - 1]
    fb, db, _ = track[i]
    return slerp(da, db, _smoothstep((f - fa) / (fb - fa)))


def layer_delta(keys, joint: str, f) -> tuple[float, float, float, float]:
    """Дельта слоя для сустава на кадре f как кватернион (w, x, y, z); identity, если ключей нет."""
    track = _normalize(keys).get(joint, [])
    q = _eval(track, [k[0] for k in track], f)
    return tuple(float(c) for c in q) if q is not None else _ID


def _names(root):
    out, stack = [], [root]
    while stack:
        j = stack.pop()
        out.append(j.name)
        stack.extend(j.children)
    return out


def _copy_frame(fr):
    return {n: {k: (list(v) if isinstance(v, list) else v) for k, v in d.items()} if isinstance(d, dict) else d
            for n, d in fr.items()}


def apply_layer(root, frames: list[dict], keys) -> list[dict]:
    """Применить слой к копии кадров: R' = R · L(f) в локальном пространстве сустава.

    Вход не меняется. Кадры без влияния слоя совпадают с исходными побитно; изменённые
    углы непрерывны по каждому суставу (continuous_euler). Неизвестный сустав или кадр
    вне клипа → ValueError.
    """
    tracks = _normalize(keys)
    n = len(frames)
    known = set(_names(root)) if root is not None else set()
    unknown = sorted(j for j in tracks if j not in known)
    if unknown:
        raise ValueError("Слой: в скелете нет суставов: " + ", ".join(unknown))
    bad = sorted({k[0] for t in tracks.values() for k in t if k[0] >= n})
    if bad:
        raise ValueError(f"Слой: кадр вне клипа (всего кадров {n}): " + ", ".join(str(b) for b in bad))
    out = [_copy_frame(fr) for fr in frames]
    for joint, track in tracks.items():
        idx = [k[0] for k in track]
        first = idx[0] - track[0][2]
        last = idx[-1] + track[-1][2]
        prev = None
        for t in range(max(0, first), min(n, last + 1)):
            q = _eval(track, idx, t)
            d = out[t].get(joint)
            base = tuple(d["rot"]) if isinstance(d, dict) and "rot" in d else None
            if q is None or tuple(q) == _ID:  # ровно identity — кадр не трогаем (побитно)
                prev = base
                continue
            R = euler_zxy_to_matrix(*(base or (0.0, 0.0, 0.0)))
            e = matrix_to_euler_zxy(matmul(R, quat_to_matrix(q)))
            e = continuous_euler(e, prev if prev is not None else base)
            if not isinstance(d, dict):
                d = out[t][joint] = {}
            d["rot"] = e
            prev = e
    return out
