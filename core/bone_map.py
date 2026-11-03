"""MoCapGate — automatic humanoid bone mapping between skeleton naming conventions.

Pure stdlib. Every bone name is reduced to a canonical humanoid role ("hips", "thigh.L",
"index2.R", spine/neck chains ...) and roles are matched between the source (MoCapGate BVH)
and the target (your character). Understood conventions:

    Mixamo        mixamorig:Hips, LeftUpLeg, LeftLeg, LeftArm, LeftForeArm, LeftHandIndex1
    UE4 / UE5     pelvis, spine_01.., thigh_l, calf_l, foot_l, ball_l, clavicle_l, upperarm_l,
                  lowerarm_l, hand_l, neck_01, head, thumb_01_l (twist/corrective/ik bones ignored)
    Unity/generic Hips, LeftUpperLeg, LeftLowerLeg, UpperArm_L, Arm.L, Left Index Proximal
    Rigify        DEF-spine (= hips), DEF-spine.001.., DEF-thigh.L, DEF-shin.L, DEF-upper_arm.L,
                  DEF-forearm.L, DEF-hand.L, DEF-f_index.01.L (".L.001" segments ignored)
    CC / iClone   CC_Base_Hip, CC_Base_Waist, CC_Base_Spine01, CC_Base_L_Thigh, CC_Base_L_Calf ...
    Daz Genesis   hip, abdomenLower, chestUpper, lThighBend, lShin, lFoot, lShldrBend, lForearmBend
    VRM / VRoid   J_Bip_C_Hips, J_Bip_C_Chest, J_Bip_L_UpperLeg, J_Bip_L_Little1 ...
    3ds Max Biped Bip01 Pelvis, Bip01 L Thigh, Bip01 L Finger01

Sides are only ever matched to the same side.
"""
from __future__ import annotations

import re

SIDES = ("L", "R")
LIMBS = ("shoulder", "upper_arm", "forearm", "hand", "thigh", "shin", "foot", "toe")
FINGERS = ("thumb", "index", "middle", "ring", "pinky")
REQUIRED = ("hips", "spine", "head") + tuple(
    f"{bone}.{side}" for side in SIDES for bone in ("upper_arm", "forearm", "hand", "thigh", "shin", "foot"))

_BODY = {
    "shoulder": "shoulder", "clavicle": "shoulder", "clav": "shoulder", "collar": "shoulder",
    "collarbone": "shoulder",
    "arm": "upper_arm", "upperarm": "upper_arm", "uparm": "upper_arm", "shldr": "upper_arm",
    "humerus": "upper_arm", "armupper": "upper_arm",
    "forearm": "forearm", "lowerarm": "forearm", "loarm": "forearm", "elbow": "forearm",
    "armlower": "forearm",
    "hand": "hand", "wrist": "hand",
    "upleg": "thigh", "upperleg": "thigh", "thigh": "thigh", "femur": "thigh", "hip": "thigh",
    "legupper": "thigh",
    "leg": "shin", "lowerleg": "shin", "calf": "shin", "shin": "shin", "knee": "shin",
    "loleg": "shin", "lowleg": "shin", "leglower": "shin",
    "foot": "foot", "ankle": "foot",
    "toe": "toe", "toes": "toe", "toebase": "toe", "ball": "toe", "toe0": "toe",
    "eye": "eye",
}
_CENTER = {"hips": ("hips", 0), "hip": ("hips", 1), "pelvis": ("hips", 2),
           "head": ("head", 0), "jaw": ("jaw", 0), "jawroot": ("jaw", 1), "lowerjaw": ("jaw", 2)}
_FINGER_WORD = {"thumb": "thumb", "index": "index", "middle": "middle", "mid": "middle",
                "ring": "ring", "pinky": "pinky", "little": "pinky"}
_SEGMENT = {"proximal": 1, "intermediate": 2, "distal": 3}
_SKIP = re.compile(r"twist|roll|corrective|helper|share|bulge|adjust|metacarpal|carpal|palm|"
                   r"metatarsal|ctrl|control|pole|target|socket|weapon|prop|attach")
_END = re.compile(r"(end|nub|tip|top|leaf)\d*$")


def strip(name: str) -> str:
    """Namespace and known rig prefixes removed, original case kept."""
    s = re.split(r"[:|]", str(name))[-1].strip()
    s = re.sub(r"^mixamorig\d*_?", "", s, flags=re.I)
    s = re.sub(r"^(def|cc_base|j_bip|bip0*1|bip)[-_ ]+", "", s, flags=re.I)
    s = re.sub(r"[-_ ]?(jnt|joint|bind|bn|def)$", "", s, flags=re.I)
    s = re.sub(r"^(jnt|bn|bone)[-_ ]", "", s, flags=re.I)
    return s


def _side(s: str):
    """→ (side or None, rest, trailing segment number or None)."""
    m = re.match(r"(?i)(left|right)", s)
    if m:
        return m.group(1)[0].upper(), s[m.end():], None
    m = re.match(r"(?i)([lr])[ _.\-]", s)
    if m:
        return m.group(1).upper(), s[m.end():], None
    m = re.match(r"([lr])(?=[A-Z])", s)  # Daz: lThighBend
    if m:
        return m.group(1).upper(), s[1:], None
    m = re.search(r"(?i)[ _.\-](l|r|left|right)(?:[._](\d+))?$", s)
    if m:
        return m.group(1)[0].upper(), s[:m.start()], (int(m.group(2)) if m.group(2) else None)
    m = re.search(r"(?i)(left|right)$", s)
    if m:
        return m.group(1)[0].upper(), s[:m.start()], None
    m = re.search(r"(?<=[a-z0-9])([LR])$", s)
    if m:
        return m.group(1), s[:m.start()], None
    return None, s, None


def _finger(body: str):
    m = re.match(r"finger(\d)(\d)?$", body)  # Biped: Finger0 = thumb, Finger01 = thumb segment 2
    if m:
        return FINGERS[int(m.group(1))] if int(m.group(1)) < 5 else None, int(m.group(2) or 0) + 1
    for word, finger in sorted(_FINGER_WORD.items(), key=lambda kv: -len(kv[0])):
        i = body.find(word)
        if i < 0:
            continue
        rest = body[i + len(word):]
        seg = next((v for k, v in _SEGMENT.items() if k in rest), None)
        if seg is None:
            m = re.search(r"(\d+)", rest)
            seg = int(m.group(1)) if m else None
        return finger, seg
    return None


def canonical(name: str, rigify: bool = False):
    """Canonical role of a bone, or None. Chains are returned as ("spine", rank) / ("neck", rank).

    Single bones: "hips", "head", "jaw", "thigh.L", "index2.R" ...; `rigify` switches the
    DEF-spine.00N meaning (spine = hips, .004/.005 neck, .006 head).
    """
    raw = str(name)
    base = re.split(r"[:|]", raw)[-1]
    if re.match(r"(?i)(org|mch|ctrl|ik|vb|j_adj|j_sec|root|boneroot|armature)([-_ .]|$)", base) \
            or re.fullmatch(r"(?i)(cc_base_)?(bone)?root|bip0*1|armature", base):
        return None
    s = strip(raw)
    side, rest, segment = _side(s)
    body = re.sub(r"[^a-z0-9]", "", rest.lower())
    body = re.sub(r"^c(?=hips|spine|chest|upperchest|neck|head)", "", body)  # VRM C_ centre marker
    if not body:
        return None
    if body.startswith("necktwist") and side is None:  # CC_Base_NeckTwist01/02 are the neck bones
        return ("neck", int(re.sub(r"\D", "", body) or 0))
    if side:
        body = re.sub(r"bend$", "", body)  # Daz ShldrBend/ForearmBend/ThighBend are the main bones
    if not body or _SKIP.search(body) or _END.search(body):
        return None
    if side:
        fing = _finger(body)
        if fing:
            finger, seg = fing
            return f"{finger}{seg}.{side}" if finger and seg in (1, 2, 3) else None
        if segment:  # Rigify DEF-upper_arm.L.001 — twist segment
            return None
        role = _BODY.get(body)
        return f"{role}.{side}" if role else None
    if body in _CENTER:
        role = _CENTER[body][0]
        return role
    m = re.fullmatch(r"spine(\d*)", body)
    if m:
        n = int(m.group(1) or 0)
        if rigify:
            if n == 0:
                return "hips"
            if n >= 6:
                return "head"
            if n >= 4:
                return ("neck", n)
        return ("spine", 10 + n)
    ranks = {"waist": 0, "abdomen": 1, "abdomenlower": 1, "abdomen1": 1, "abdomenupper": 2, "abdomen2": 2,
             "lowerspine": 5, "upperspine": 25, "chest": 30, "chestlower": 30, "chest1": 30,
             "upperchest": 31, "chestupper": 31, "chest2": 31}
    if body in ranks:
        return ("spine", ranks[body])
    m = re.fullmatch(r"neck(\d*)|neck(lower|upper)", body)
    if m:
        return ("neck", {"lower": 1, "upper": 2}.get(m.group(2) or "", int(m.group(1) or 0)))
    return None


def _is_rigify(names) -> bool:
    bodies = {re.sub(r"[^a-z0-9.]", "", strip(n).lower()) for n in names}
    return any(re.fullmatch(r"spine\.00[1-6]", b) for b in bodies) and not any(canonical(n) == "hips" for n in names)


def roles(names) -> dict:
    """{role: bone name} for single roles plus {"spine": [...], "neck": [...]} ordered chains."""
    rigify = _is_rigify(names)
    single, prio, chains = {}, {}, {"spine": [], "neck": []}
    for name in names:
        role = canonical(name, rigify)
        if role is None:
            continue
        if isinstance(role, tuple):
            chains[role[0]].append((role[1], name))
            continue
        body = re.sub(r"[^a-z0-9]", "", strip(name).lower())
        p = _CENTER.get(body, (None, 5))[1] if role in ("hips", "head", "jaw") else 0
        if role not in single or p < prio[role]:
            single[role], prio[role] = name, p
    for key, items in chains.items():
        single[key] = [n for _, n in sorted(items, key=lambda t: t[0])]
    return single


def _distribute(src: list, dst: list) -> dict:
    ns, nt = len(src), len(dst)
    if not ns or not nt:
        return {}
    if ns == 1 or nt == 1:
        return {src[0]: dst[0]}
    if ns <= nt:
        return {src[i]: dst[round(i * (nt - 1) / (ns - 1))] for i in range(ns)}
    return {src[round(j * (ns - 1) / (nt - 1))]: dst[j] for j in range(nt)}


def auto_map(source_names, target_names, overrides: dict | None = None):
    """Map humanoid bones of `source_names` onto `target_names`.

    Returns (mapping, unmapped_required): mapping is {source bone: target bone}; the list names
    required canonical roles (see REQUIRED, e.g. "shin.L") that ended up without a mapping.
    `overrides` ({source: target}, target None/"" removes) are applied on top.
    """
    source_names, target_names = list(source_names), list(target_names)
    src, dst = roles(source_names), roles(target_names)
    mapping: dict = {}
    for role, s in src.items():
        if role in ("spine", "neck"):
            mapping.update(_distribute(s, dst.get(role) or []))
        elif role in dst:
            mapping[s] = dst[role]
    # Non-humanoid extras (twist bones, eyes ...) map by identical names when both skeletons have them.
    used = set(mapping.values())
    key = lambda n: re.sub(r"[^a-z0-9]", "", strip(n).lower())  # noqa: E731
    by_key = {}
    for t in target_names:
        by_key.setdefault(key(t), t)
    for s in source_names:
        t = by_key.get(key(s))
        if s not in mapping and t and t not in used and canonical(s) is None and canonical(t) is None \
                and not _END.search(key(s)):
            mapping[s] = t
            used.add(t)
    for s, t in (overrides or {}).items():
        if s not in source_names:
            continue
        if not t:
            mapping.pop(s, None)
        elif t in target_names:
            for other in [k for k, v in mapping.items() if v == t]:
                del mapping[other]
            mapping[s] = t
    mapped_roles = {canonical(s, _is_rigify(source_names)) for s in mapping}
    unmapped = []
    for role in REQUIRED:
        if role == "spine":
            ok = any(isinstance(r, tuple) and r[0] == "spine" for r in mapped_roles)
        else:
            ok = role in mapped_roles
        if not ok:
            unmapped.append(role)
    return mapping, unmapped
