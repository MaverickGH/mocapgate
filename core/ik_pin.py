"""MoCapGate — закрепление кисти или стопы в точке (IK pin) на stdlib.

Кисть лежит на столе, рука держит предмет, стопа стоит на ступеньке: на отрезке кадров
first..last конечный сустав остаётся ровно в целевой точке, руку/ногу доводит аналитический
IK из двух звеньев (плечо→локоть→кисть или бедро→колено→стопа). Плоскость сгиба локтя/колена
берётся из текущего положения среднего сустава, поэтому характер позы сохраняется. За blend
секунд до и после отрезка эффект плавно нарастает и спадает (smoothstep), дальше кадры не
меняются.

Кадр: {имя: {'rot': (z, x, y) градусы ZXY, R = Rz·Rx·Ry, 'pos': (x, y, z) см у корня}}, Y вверх.
Имена ищутся без учёта префикса (mixamorig:LeftHand). Твист-суставы между звеньями
(LeftArmTwist, LeftForeArmTwist, LeftUpLegTwist) сохраняют свой локальный поворот.
"""
from __future__ import annotations
import math

from core.motion_cleanup import (
    _I, _add, _axis_angle, _base, _cross, _dot, _euler_m, _flat, _fk, _len, _mm, _mt, _mv, _rot_between,
    _smoothstep, _sub,
)
from core.rotations import continuous_euler, matrix_to_euler_zxy, matrix_to_quat, quat_to_matrix, slerp

EFFECTORS = ("LeftHand", "RightHand", "LeftFoot", "RightFoot")
_CHAIN = {
    "Hand": (("Arm", "UpperArm"), ("ForeArm", "LowerArm")),
    "Foot": (("UpLeg", "UpperLeg"), ("Leg", "LowerLeg")),
}


def _find_any(root, names):
    stack = [root]
    while stack:
        j = stack.pop()
        if _base(j.name) in names:
            return j
        stack.extend(j.children)
    return None


def _path_to(root, name):
    if root.name == name:
        return [root.name]
    for c in root.children:
        p = _path_to(c, name)
        if p:
            return [root.name] + p
    return None


def _chain(root, effector):
    """(путь от корня до эффектора, верхний, средний, эффектор) или ValueError."""
    if effector not in EFFECTORS:
        raise ValueError(f"Неизвестный эффектор {effector!r}: допустимы {', '.join(EFFECTORS)}")
    side, kind = ("Left", effector[4:]) if effector.startswith("Left") else ("Right", effector[5:])
    ups, mids = _CHAIN[kind]
    eff = _find_any(root, {effector})
    up = _find_any(root, {side + n for n in ups})
    mid = _find_any(root, {side + n for n in mids})
    if not (eff and up and mid):
        raise ValueError(f"В скелете нет цепочки для {effector}: нужны {side}{ups[0]}, {side}{mids[0]}, {effector}")
    path = _path_to(root, eff.name)
    if not path or up.name not in path or mid.name not in path or not (
            path.index(up.name) < path.index(mid.name) < path.index(eff.name)):
        raise ValueError(f"Цепочка {up.name} → {mid.name} → {eff.name} не является ветвью иерархии")
    return path, up.name, mid.name, eff.name


def _vec3(v, what):
    try:
        out = tuple(float(c) for c in v)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: ожидается [x, y, z] в сантиметрах") from None
    if len(out) != 3 or not all(math.isfinite(c) for c in out):
        raise ValueError(f"{what}: ожидается [x, y, z] из трёх конечных чисел")
    return out


def _int(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v):
        raise ValueError(f"{what}: ожидается целый номер кадра")
    return int(v)


def _copy(frames):
    return [{k: dict(v) if isinstance(v, dict) else v for k, v in fr.items()} for fr in frames]


def _solve(hip, knee, ank, T, fallback):
    """Два звена: (dH, dK, n, достижимо). dK — поворот среднего сустава в мире вокруг колена/локтя,
    dH — поворот всей цепочки вокруг верхнего сустава; плоскость сгиба сохраняется."""
    u, v = _sub(hip, knee), _sub(ank, knee)
    la, lb = _len(u), _len(v)
    if la < 1e-6 or lb < 1e-6:
        return _I, _I, None, True
    dist = _len(_sub(T, hip))
    lo, hi = abs(la - lb) + 1e-3, la + lb - 1e-4
    reach = lo - 1e-6 <= dist <= la + lb + 1e-6
    d = min(max(dist, lo), hi)
    cur = math.acos(max(-1.0, min(1.0, _dot(u, v) / (la * lb))))
    new = math.acos(max(-1.0, min(1.0, (la * la + lb * lb - d * d) / (2 * la * lb))))
    nrm = _cross(u, v)
    ln = _len(nrm)
    if ln < 1e-4 * la * lb:  # звено выпрямлено: ось сгиба с прошлого кадра или по умолчанию
        nrm = fallback
        ln = _len(nrm)
    n = (nrm[0] / ln, nrm[1] / ln, nrm[2] / ln)
    dK = _axis_angle(n, new - cur)
    a1 = _add(knee, _mv(dK, v))
    e = _sub(T, hip)
    if _len(e) < 1e-6:
        return _I, dK, n, reach
    dH = _rot_between(_sub(a1, hip), e)
    le = _len(e)
    e = (e[0] / le, e[1] / le, e[2] / le)
    k2, k0 = _mv(dH, _sub(knee, hip)), _sub(knee, hip)
    p2 = _sub(k2, tuple(c * _dot(k2, e) for c in e))
    p0 = _sub(k0, tuple(c * _dot(k0, e) for c in e))
    if _len(p2) > 1e-6 and _len(p0) > 1e-6:  # средний сустав — обратно в исходную плоскость
        dH = _mm(_axis_angle(e, math.atan2(_dot(_cross(p2, p0), e), _dot(p2, p0))), dH)
    return dH, dK, n, reach


def pin(root, frames: list[dict], fps: float, effector: str, first: int, last: int, target=None,
        blend: float = 0.15, keep_orientation: bool = True):
    """Закрепить кисть/стопу в мировой точке на кадрах first..last (с 0, включительно).

    target — [x, y, z] см, по умолчанию положение эффектора в кадре first. blend — секунды плавного
    входа и выхода за пределами отрезка. keep_orientation — эффектор держит мировую ориентацию
    кадра first. Меняются только повороты суставов цепочки; входные кадры не изменяются.
    Возвращает (frames, info): info = {effector, frames (изменено кадров), max_error_cm
    (наибольшее расстояние эффектор→цель на отрезке), unreachable_frames (цель вне досягаемости,
    эффектор доведён до предела вытянутой цепочки)}.
    """
    path, up, mid, eff = _chain(root, effector)
    n = len(frames)
    if not n:
        raise ValueError("Нет кадров для закрепления")
    first, last = _int(first, "first"), _int(last, "last")
    if not (0 <= first <= last < n):
        raise ValueError(f"Неверный диапазон кадров {first}..{last}: допустимо 0..{n - 1}, first ≤ last")
    try:
        fps, blend = float(fps), float(blend)
    except (TypeError, ValueError):
        raise ValueError("fps и blend должны быть числами") from None
    if not (math.isfinite(fps) and fps > 0):
        raise ValueError("fps должен быть больше нуля")
    if not (math.isfinite(blend) and blend >= 0):
        raise ValueError("blend должен быть неотрицательным числом секунд")

    flat = _flat(root, keep=set(path))
    out = _copy(frames)
    pos0, rot0 = _fk(flat, frames[first])
    T = _vec3(target, "target") if target is not None else pos0[eff]
    q_pin = matrix_to_quat(rot0[eff])
    nb = int(round(blend * fps))
    a, b = max(0, first - nb), min(n - 1, last + nb)
    chain = path[path.index(up):]
    leg = effector.endswith("Foot")
    info = {"effector": effector, "frames": 0, "max_error_cm": 0.0, "unreachable_frames": 0}
    prev_n = None

    for t in range(a, b + 1):
        if t < first:
            w = _smoothstep(1 - (first - t) / (nb + 1))
        elif t > last:
            w = _smoothstep(1 - (t - last) / (nb + 1))
        else:
            w = 1.0
        if w <= 0:
            continue
        fr = out[t]
        pos, rot = _fk(flat, fr)
        src = pos[eff]
        goal = (src[0] + w * (T[0] - src[0]), src[1] + w * (T[1] - src[1]), src[2] + w * (T[2] - src[2]))
        if prev_n is not None:
            fb = prev_n
        elif leg:  # колено вперёд: минус локальная X голени, как в foot_lock
            g = rot[mid]
            fb = (-g[0][0], -g[1][0], -g[2][0])
        else:  # локоть: сгиб вперёд по направлению корня
            g = rot[path[0]]
            fwd = (g[0][2], g[1][2], g[2][2])
            fb = _cross(fwd, _sub(pos[eff], pos[mid]))
            if _len(fb) < 1e-9:
                fb = (0.0, 1.0, 0.0)
        dH, dK, nv, reach = _solve(pos[up], pos[mid], pos[eff], goal, fb)
        if nv is not None:
            prev_n = nv
        if not reach and first <= t <= last:
            info["unreachable_frames"] += 1
        # новые мировые повороты цепочки; твисты и прочие промежуточные суставы держат локальный
        W_mid = _mm(dH, _mm(dK, rot[mid]))
        W_eff = _mm(dH, _mm(dK, rot[eff]))
        if keep_orientation:
            W_eff = quat_to_matrix(slerp(matrix_to_quat(W_eff), q_pin, w))
        i_up = path.index(up)
        parent = rot[path[i_up - 1]] if i_up > 0 else _I
        world = parent
        for name in chain:
            if name == up:
                W = _mm(dH, rot[up])
            elif name == mid:
                W = W_mid
            elif name == eff:
                if not keep_orientation:  # локальный поворот кисти/стопы остаётся как был
                    break
                W = W_eff
            else:
                W = _mm(world, _euler_m((fr.get(name) or {}).get("rot", (0.0, 0.0, 0.0))))
                world = W
                continue
            local = _mm(_mt(world), W)
            d = fr.setdefault(name, {})
            ref = out[t - 1].get(name, {}).get("rot") if t > 0 else None
            ref = tuple(ref) if ref is not None else tuple(d.get("rot", (0.0, 0.0, 0.0)))
            d["rot"] = continuous_euler(matrix_to_euler_zxy(local), ref)
            world = W
        info["frames"] += 1

    worst = 0.0
    for t in range(first, last + 1):
        p = _fk(flat, out[t])[0][eff]
        worst = max(worst, _len(_sub(p, T)))
    info["max_error_cm"] = round(worst, 4)
    return out, info


def pins_apply(root, frames: list[dict], fps: float, pins):
    """Применить список закреплений по очереди (формат JSON шага «Применить правки»).

    pins — [{'effector', 'first', 'last', 'target'?: [x, y, z], 'blend'?: сек,
    'keep_orientation'?: bool}, ...]. Возвращает (frames, [info, ...]).
    """
    if pins is None:
        return _copy(frames), []
    if not isinstance(pins, (list, tuple)):
        raise ValueError("pins: ожидается список закреплений")
    infos = []
    out = frames
    for i, p in enumerate(pins):
        if not isinstance(p, dict):
            raise ValueError(f"Закрепление №{i + 1}: ожидается объект с effector, first, last")
        missing = [k for k in ("effector", "first", "last") if k not in p]
        if missing:
            raise ValueError(f"Закрепление №{i + 1}: нет полей {', '.join(missing)}")
        kw = {}
        if p.get("blend") is not None:
            kw["blend"] = p["blend"]
        if p.get("keep_orientation") is not None:
            kw["keep_orientation"] = bool(p["keep_orientation"])
        out, info = pin(root, out, fps, p["effector"], p["first"], p["last"], p.get("target"), **kw)
        infos.append(info)
    if not pins:
        out = _copy(frames)
    return out, infos
