"""MoCapGate — script inside Blender: retarget a MoCapGate BVH onto your own character.

    blender -b --factory-startup -P core/blender_retarget.py -- \
        --bvh take.bvh --character hero.fbx --out hero_take.fbx [--map overrides.json] \
        [--face take.face.csv] [--in-place] [--align-threshold 15] [--no-foot-ik]

Character: .fbx, .glb/.gltf or .blend (objects appended). Its armature is the one with the most bones.
Bones are matched by core.bone_map (Mixamo, UE, Unity, Rigify, CC, Daz, VRM ... names); --map is a
JSON {source: target} (or {"mapping": {...}}) applied on top.

Alignment: every mapped target bone gets the source bone's world-space rotation change since its rest
pose. Before that the target's rest is brought into the source's rest pose with a per-bone swing
(bone direction → direction of the source bone), so an A-pose character follows a T-pose source; bones
without a single mapped child inherit their parent's swing, and differences below --align-threshold
degrees (default 15) are left alone so the source's rest anatomy is not copied. A yaw aligns the two skeletons' facing.
The hips move with the source, scaled by the leg-length ratio (hips height above the feet); the floor
is the lowest foot/toe of the source over the clip and of the character at rest.

Foot IK (on by default, --no-foot-ik turns it off; pure math in core/leg_ik.py): the source ball of the foot
is mapped into the character's space like the hips (same ratio and floor) and corrected by the rest-pose
difference of the skeletons along the pelvis lateral/forward axes and in height (hip width, foot placement,
height above the sole); the ankle target adds the character's own ball→ankle vector, so foot length and
ankle height stay the character's. Flat-foot contacts of the source (ankle and toe low and slow, hysteresis,
minimum duration) are locked to one point each (mean of the span, cosine blend in/out); between contacts the
plain rotation transfer is kept. A two-bone IK (law of cosines) puts the character's ankle on the target with
the knee in the source knee plane; the foot keeps the source world rotation. Out-of-reach targets lower the
hips (smoothed) instead of overstretching the knee. The result reports foot_slide_cm {before, after}: mean
horizontal path of the ankle per contact, plain rotation transfer vs. the baked result.

Output: FBX (mesh, skinning, animation and shape keys, no leaf bones; Y up, -Z forward) or GLB.
Prints MOCAPGATE_RESULT {json}.
"""
import json
import math
import re
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Matrix, Quaternion, Vector  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import bone_map, leg_ik  # noqa: E402


def args() -> dict:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out, key = {}, None
    for a in argv:
        if a.startswith("--"):
            key = a[2:]
            out[key] = True
        elif key:
            out[key] = a
            key = None
    return out


def fcurves_of(action, anim_data):
    """Action F-curves in Blender 3.x/4.x and in Blender 5 (channelbag of the slot)."""
    if hasattr(action, "fcurves"):
        return action.fcurves
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(action, anim_data.action_slot).fcurves


def import_character(path: Path):
    before = set(bpy.data.objects)
    ext = path.suffix.lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".blend":
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for obj in dst.objects:
            if obj is not None and obj.name not in bpy.context.scene.collection.all_objects:
                bpy.context.scene.collection.objects.link(obj)
    else:
        raise ValueError(f"Unsupported character format: {ext} (use .fbx, .glb, .gltf or .blend)")
    objects = [o for o in bpy.data.objects if o not in before]
    arms = [o for o in objects if o.type == "ARMATURE"]
    if not arms:
        raise ValueError("No armature found in the character file")
    return max(arms, key=lambda o: len(o.data.bones)), objects


def import_bvh(path: Path):
    header = re.search(r"Frame Time:\s*([0-9.eE+-]+)", path.read_text(encoding="utf-8"))
    if not header or float(header.group(1)) <= 0:
        raise ValueError("BVH frame time is missing or invalid")
    rate = 1.0 / float(header.group(1))
    scene = bpy.context.scene
    scene.render.fps = max(1, round(rate))
    scene.render.fps_base = scene.render.fps / rate
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=str(path), global_scale=0.01, use_fps_scale=False, update_scene_fps=False,
                            update_scene_duration=True, rotate_mode="NATIVE", axis_forward="-Z", axis_up="Y")
    src = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
    start, end = (int(round(v)) for v in src.animation_data.action.frame_range)
    scene.frame_start, scene.frame_end = start, end
    return src, start, end


def rot(m):
    return m.to_3x3().normalized().to_quaternion()


def roles_of(names):
    rigify = bone_map._is_rigify(names)
    return {n: bone_map.canonical(n, rigify) for n in names}


def lowest(obj, names, posed):
    zs = [(obj.matrix_world @ (obj.pose.bones[n].head if posed else obj.data.bones[n].head_local)).z for n in names]
    return min(zs) if zs else None


def feet(role_map):
    return [n for n, r in role_map.items() if isinstance(r, str) and r.split(".")[0] in ("foot", "toe")]


def depth(bone):
    return len(bone.parent_recursive)


def retarget(src, tgt, mapping, start, end, in_place=False, align_threshold=15.0, foot_ik=True):
    scene = bpy.context.scene
    s_roles, t_roles = roles_of([b.name for b in src.data.bones]), roles_of([b.name for b in tgt.data.bones])
    s_mw, t_mw = src.matrix_world.copy(), tgt.matrix_world.copy()
    t_rot_inv = rot(t_mw).inverted()
    s_rest = {n: s_mw @ src.data.bones[n].matrix_local for n in mapping}
    t_rest = {t: t_mw @ tgt.data.bones[t].matrix_local for t in mapping.values()}

    def head(obj, mw, name):
        return mw @ obj.data.bones[name].head_local

    # facing: yaw that turns the character's left→right axis onto the source's
    yaw = Quaternion()
    inv = {v: k for k, v in mapping.items()}
    for pair in (("thigh.L", "thigh.R"), ("upper_arm.L", "upper_arm.R")):
        sl = [n for n in mapping if s_roles.get(n) in pair]
        if len(sl) == 2:
            a, b = sorted(sl, key=lambda n: s_roles[n] != pair[0])
            vs = head(src, s_mw, a) - head(src, s_mw, b)
            vt = head(tgt, t_mw, mapping[a]) - head(tgt, t_mw, mapping[b])
            vs.z = vt.z = 0
            if vs.length > 1e-6 and vt.length > 1e-6:
                yaw = Quaternion((0, 0, 1), math.atan2(vt.cross(vs).z, vt.dot(vs)))
            break

    # per-bone swing that puts the target rest into the source rest pose
    swing = {}
    for s in sorted(mapping, key=lambda n: depth(src.data.bones[n])):
        sb = src.data.bones[s]
        kids, best = [], None
        for c in sb.children_recursive:
            r = s_roles.get(c.name)
            if c.name not in mapping or r in ("jaw", "eye.L", "eye.R"):
                continue
            d = depth(c)
            if best is None or d < best:
                kids, best = [c.name], d
            elif d == best:
                kids.append(c.name)
        anc = next((p.name for p in sb.parent_recursive if p.name in swing), None)
        swing[s] = swing[anc].copy() if anc else Quaternion()
        if len(kids) == 1 and tgt.data.bones[mapping[kids[0]]] in tgt.data.bones[mapping[s]].children_recursive:
            ds = head(src, s_mw, kids[0]) - head(src, s_mw, s)
            dt = yaw @ (head(tgt, t_mw, mapping[kids[0]]) - head(tgt, t_mw, mapping[s]))
            # only real pose differences (A- vs T-pose arms, spread legs) are corrected; small anatomical
            # differences of the rest skeletons (knock knees, slight elbow bend) are not copied
            if ds.length > 1e-6 and dt.length > 1e-6 and \
                    (swing[s] @ dt).angle(ds) > math.radians(align_threshold):
                swing[s] = dt.normalized().rotation_difference(ds.normalized())
    offset = {s: rot(s_rest[s]).inverted() @ swing[s] @ yaw @ rot(t_rest[t]) for s, t in mapping.items()}

    # hips translation: leg-length ratio, floors from feet/toes
    hips_s = next((n for n in mapping if s_roles.get(n) == "hips"), None)
    if hips_s is None:  # fall back to the mapped bone nearest to the root
        hips_s = min(mapping, key=lambda n: depth(src.data.bones[n]))
    hips_t = mapping[hips_s]
    s_feet = [n for n in feet(s_roles)]
    t_feet = [n for n in feet(t_roles)]
    s_hips_rest, t_hips_rest = head(src, s_mw, hips_s), head(tgt, t_mw, hips_t)
    s_rest_floor = lowest(src, s_feet, False) if s_feet else None
    s_leg = s_hips_rest.z - s_rest_floor if s_feet else None
    t_floor = lowest(tgt, t_feet, False) if t_feet else 0.0
    t_leg = t_hips_rest.z - t_floor
    ratio = t_leg / s_leg if s_leg and s_leg > 1e-6 and t_leg > 1e-6 else 1.0

    # legs with mapped thigh, shin and foot forming one chain in the character; the bones whose world rotation
    # carries the thigh (thigh … up to the shin) and the shin (shin … up to the foot)
    def path(top, bottom):
        out, b = [], tgt.data.bones[bottom].parent
        while b is not None:
            if b.name in t_src:
                out.append(b.name)
            if b.name == top:
                return out
            b = b.parent
        return None

    t_src = {t: s for s, t in mapping.items()}
    legs = {}
    for side in ("L", "R"):
        bones = [next((n for n in mapping if s_roles.get(n) == f"{r}.{side}"), None) for r in ("thigh", "shin", "foot")]
        if not all(bones):
            continue
        thigh_path, shin_path = path(mapping[bones[0]], mapping[bones[1]]), path(mapping[bones[1]], mapping[bones[2]])
        if thigh_path and shin_path:
            toe = next((n for n in sorted(s_roles) if s_roles[n] == f"toe.{side}"), None)
            t_toe = next((b.name for b in tgt.data.bones[mapping[bones[2]]].children_recursive
                          if t_roles.get(b.name) == f"toe.{side}"), None)
            legs[side] = {"src": bones, "toe": toe, "tgt": [mapping[n] for n in bones], "t_toe": t_toe,
                          "thigh_fix": thigh_path, "shin_fix": shin_path}

    # sample the source once: world rotations of mapped bones and the joint positions the legs need
    s_points = {hips_s} | {n for leg in legs.values() for n in leg["src"] + [leg["toe"]] if n}
    frames = list(range(start, end + 1))
    cache, s_floor = {}, None
    for f in frames:
        scene.frame_set(f)
        cache[f] = ({s: rot(s_mw @ src.pose.bones[s].matrix) for s in mapping},
                    {n: s_mw @ src.pose.bones[n].head for n in s_points})
        if s_feet:
            z = lowest(src, s_feet, True)
            s_floor = z if s_floor is None else min(s_floor, z)
    if s_floor is None:
        s_floor = s_hips_rest.z - (s_leg or 0)

    def to_target(p, hips=None):
        """Source world point → character world point: about the hips, scaled by the leg-length ratio,
        floor on floor; hips — the source hips of the frame, removes root motion for --in-place."""
        q = Vector((t_hips_rest.x + ratio * (p.x - s_hips_rest.x), t_hips_rest.y + ratio * (p.y - s_hips_rest.y),
                    t_floor + ratio * (p.z - s_floor)))
        if in_place and hips is not None:
            q.x -= ratio * (hips.x - s_hips_rest.x)
            q.y -= ratio * (hips.y - s_hips_rest.y)
        return q

    # target pose, parents first
    ad = tgt.animation_data_create()
    ad.action = None
    for track in list(ad.nla_tracks):
        ad.nla_tracks.remove(track)
    order = sorted(tgt.pose.bones, key=lambda pb: depth(pb.bone))
    rest_rel = {pb.name: (pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local) if pb.parent
                else pb.bone.matrix_local.copy() for pb in order}
    for pb in order:
        pb.matrix_basis = Matrix()
    for pb in order:
        if pb.name in t_src:
            pb.rotation_mode = "QUATERNION"
    t_mw_inv = t_mw.inverted()

    def solve(f, drop=0.0, fix=None):
        """Поза кадра: матрицы костей в пространстве арматуры и basis анимируемых костей. drop — опускание
        таза (м), fix — мировые поправки поворота {кость: Quaternion} поверх перенесённого поворота."""
        rots, heads = cache[f]
        pose, basis = {}, {}
        for pb in order:
            base = (pose[pb.parent.name] @ rest_rel[pb.name]) if pb.parent else rest_rel[pb.name]
            s = t_src.get(pb.name)
            if s is None:
                pose[pb.name] = base
                continue
            world = rots[s] @ offset[s]
            if fix and pb.name in fix:
                world = fix[pb.name] @ world
            arm_rot = (t_rot_inv @ world).to_matrix().to_4x4()
            if pb.name == hips_t:
                pos = to_target(heads[hips_s], heads[hips_s])
                pos.z -= drop
                loc = t_mw_inv @ pos
            else:
                loc = base.translation
            basis[pb.name] = base.inverted() @ (Matrix.Translation(loc) @ arm_rot)
            pose[pb.name] = base @ basis[pb.name]
        return pose, basis

    prev = {}

    def key(f, basis):
        for name, b in basis.items():
            pb = tgt.pose.bones[name]
            q = b.to_quaternion()
            if name in prev and prev[name].dot(q) < 0:
                q.negate()
            prev[name] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f, group=name)
            if name == hips_t:
                pb.location = b.translation
                pb.keyframe_insert("location", frame=f, group=name)

    # pass 1: plain rotation transfer; joint positions of the character's legs
    ik = foot_ik and bool(legs)
    tup = lambda v: (v.x, v.y, v.z)  # noqa: E731
    fk = {side: [] for side in legs}
    for f in frames:
        pose, basis = solve(f)
        if not ik:
            key(f, basis)
        for side, leg in legs.items():
            fk[side].append([tup(t_mw @ pose[n].translation) for n in leg["tgt"] + [leg["t_toe"]] if n])

    # contacts from the source feet mapped to the character; slide measured in world space (root motion back)
    fps = scene.render.fps / scene.render.fps_base
    shift = [(ratio * (cache[f][1][hips_s].x - s_hips_rest.x), ratio * (cache[f][1][hips_s].y - s_hips_rest.y), 0.0)
             if in_place else (0.0, 0.0, 0.0) for f in frames]
    spans, slide = {}, {"before": [0.0, 0], "after": [0.0, 0]}
    for side, leg in legs.items():
        ankle = [tup(to_target(cache[f][1][leg["src"][2]])) for f in frames]
        toe = [tup(to_target(cache[f][1][leg["toe"]])) for f in frames] if leg["toe"] else None
        spans[side] = leg_ik.detect_contacts(ankle, toe, fps)
        slide["before"][0] += len(spans[side]) * leg_ik.foot_slide(
            [leg_ik.add(p[2], d) for p, d in zip(fk[side], shift)], spans[side])
        slide["before"][1] += len(spans[side])

    drops = [0.0] * len(frames)
    if ik:
        # foot targets: the mapped source ball of the foot (toe joint; the ankle when either skeleton has no toe)
        # plus the rest-pose difference of the two skeletons, so the character's own proportions stand where the
        # source stands — hip width and the foot's place under the hip along the pelvis lateral/forward axes
        # (turning with the source pelvis), its height above the sole. The ankle target is then that point plus
        # the character's own ball→ankle vector, which follows the foot rotation copied from the source: foot
        # length and ankle height of the character are kept and the sole lands where the source sole is
        reach = 0.9999
        targets = {}
        up = Vector((0, 0, 1))

        def axes(obj, mw, names):
            lat = head(obj, mw, names["L"][0]) - head(obj, mw, names["R"][0]) if len(names) == 2 else Vector()
            lat.z = 0
            lat = lat.normalized() if lat.length > 1e-6 else Vector()
            return lat, up.cross(lat)

        s_axes = axes(src, s_mw, {k: v["src"] for k, v in legs.items()})
        t_axes = axes(tgt, t_mw, {k: v["tgt"] for k, v in legs.items()})
        for side, leg in legs.items():
            ball = bool(leg["toe"] and leg["t_toe"])
            s_pt, t_pt = (leg["toe"], leg["t_toe"]) if ball else (leg["src"][2], leg["tgt"][2])
            s_rel, t_rel = head(src, s_mw, s_pt) - s_hips_rest, head(tgt, t_mw, t_pt) - t_hips_rest
            d_lat, d_fwd = (t_rel.dot(ta) - ratio * s_rel.dot(sa) for sa, ta in zip(s_axes, t_axes))
            lift = (head(tgt, t_mw, t_pt).z - t_floor) - ratio * (head(src, s_mw, s_pt).z - s_rest_floor)
            points = []
            for i, f in enumerate(frames):
                h = cache[f][1]
                lat = (h[legs["L"]["src"][0]] - h[legs["R"]["src"][0]]) if len(legs) == 2 else Vector()
                lat.z = 0
                lat = lat.normalized() if lat.length > 1e-6 else Vector()
                p = tup(to_target(h[s_pt]) + lat * d_lat + up.cross(lat) * d_fwd + up * lift)
                points.append(leg_ik.add(p, leg_ik.sub(fk[side][i][2], fk[side][i][3])) if ball else p)
            # IK weight: 1 on a contact, blended over the neighbouring frames, 0 in the swing, where the plain
            # rotation transfer already gives the source's knee angle (positions would change it with the
            # character's segment proportions)
            blend = max(2, round(0.2 * fps))
            locked = leg_ik.lock_contacts(points, spans[side], blend)
            weight, _ = leg_ik.contact_weights(len(frames), spans[side], blend)
            targets[side] = [leg_ik.lerp(fk[side][i][2], leg_ik.sub(p, shift[i]), weight[i])
                             for i, p in enumerate(locked)]
            for i, (hip, knee, ank) in enumerate(p[:3] for p in fk[side]):
                limit = reach * (leg_ik.length(leg_ik.sub(knee, hip)) + leg_ik.length(leg_ik.sub(ank, knee)))
                drops[i] = max(drops[i], leg_ik.hip_drop(hip, targets[side][i], limit))
        drops = leg_ik.smooth_max(drops, max(1, round(0.2 * fps)))

        # pass 2: two-bone IK per leg, knee in the source knee plane; foot keeps its world rotation (absolute)
        poles = {}
        for i, f in enumerate(frames):
            fix = {}
            for side, leg in legs.items():
                hip, knee, ank = (leg_ik.sub(p, (0.0, 0.0, drops[i])) for p in fk[side][i][:3])
                thigh, shin = leg_ik.sub(knee, hip), leg_ik.sub(ank, knee)
                la, lb = leg_ik.length(thigh), leg_ik.length(shin)
                h = cache[f][1]
                s_hip, s_knee, s_ank = (tup(h[n]) for n in leg["src"])
                for pole in (leg_ik.perpendicular(leg_ik.sub(s_knee, s_hip), leg_ik.sub(s_ank, s_hip)),
                             leg_ik.perpendicular(thigh, leg_ik.sub(targets[side][i], hip)), poles.get(side)):
                    if pole is not None and leg_ik.length(pole) > 1e-3 * la:
                        poles[side] = pole
                        break
                pole = poles.get(side, (0.0, -1.0, 0.0))
                knee1, ank1, _ = leg_ik.two_bone_ik(hip, la, lb, targets[side][i], pole, reach)
                n0 = leg_ik.cross(thigh, shin)
                if leg_ik.length(n0) < 1e-4 * la * lb:
                    n0 = leg_ik.cross(thigh, pole)
                n1 = leg_ik.cross(leg_ik.sub(knee1, hip), leg_ik.sub(ank1, knee1))
                q_thigh = Matrix(leg_ik.frame_rotation(thigh, n0, leg_ik.sub(knee1, hip), n1)).to_quaternion()
                q_shin = Matrix(leg_ik.frame_rotation(shin, n0, leg_ik.sub(ank1, knee1), n1)).to_quaternion()
                fix.update({n: q_thigh for n in leg["thigh_fix"]})
                fix.update({n: q_shin for n in leg["shin_fix"]})
            key(f, solve(f, drops[i], fix)[1])

    if ad.action:
        ad.action.name = f"{tgt.name}_MoCapGate"
    # slide after: the character's evaluated ankles (read back from the baked action)
    for side, leg in legs.items():
        if not ik:
            break
        ankle = []
        for i, f in enumerate(frames):
            scene.frame_set(f)
            ankle.append(leg_ik.add(tup(t_mw @ tgt.pose.bones[leg["tgt"][2]].head), shift[i]))
        slide["after"][0] += len(spans[side]) * leg_ik.foot_slide(ankle, spans[side])
        slide["after"][1] += len(spans[side])
    if not ik:
        slide["after"] = slide["before"]
    cm = {k: round(100 * s / n, 2) if n else 0.0 for k, (s, n) in slide.items()}
    return {"ratio": round(ratio, 5), "yaw_deg": round(math.degrees(2 * math.acos(min(1.0, abs(yaw.w)))), 3),
            "foot_ik": ik, "foot_contacts": {s: len(v) for s, v in spans.items()}, "foot_slide_cm": cm,
            "hips_drop_cm": round(100 * max(drops, default=0.0), 2)}


def _key(name: str) -> str:
    s = re.split(r"[.:|]", name)[-1]
    s = re.sub(r"^(?:[A-Z]\d\d_|(?:blendshape\d*|face|arkit|bs|shape)[_ ])", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def apply_face(meshes, csv_path, start):
    import csv
    with open(csv_path, encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    names, rows = rows[0][2:], [r for r in rows[1:] if r]
    want = {_key(n): i for i, n in enumerate(names)}
    matched, curves = set(), 0
    for obj in meshes:
        keys = obj.data.shape_keys
        if not keys:
            continue
        hits = [(kb, want[_key(kb.name)]) for kb in keys.key_blocks[1:] if _key(kb.name) in want]
        if not hits:
            continue
        ad = keys.animation_data_create()
        ad.action = None
        for kb, i in hits:
            kb.value = float(rows[0][i + 2])
            kb.keyframe_insert("value", frame=start)
        fcurves = fcurves_of(ad.action, ad)
        for kb, i in hits:
            curve = fcurves.find(f'key_blocks["{kb.name}"].value')
            curve.keyframe_points.add(len(rows) - 1)
            for k, row in enumerate(rows):
                point = curve.keyframe_points[k]
                point.co = point.handle_left = point.handle_right = (start + k, float(row[i + 2]))
                point.interpolation = "LINEAR"
            curve.update()
            matched.add(names[i])
            curves += 1
        ad.action.name = f"{obj.name}_FaceExpressions"
    return sorted(matched), curves


def export(out: Path, objects, arm):
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        if o.name in bpy.context.view_layer.objects:
            o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    ext = out.suffix.lower()
    if ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"ARMATURE", "MESH", "EMPTY"},
                                 add_leaf_bones=False, use_mesh_modifiers=False, bake_anim=True,
                                 bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_simplify_factor=0.0, axis_forward="-Z", axis_up="Y",
                                 apply_unit_scale=True, armature_nodetype="NULL")
    elif ext in (".glb", ".gltf"):
        wanted = {"export_format": "GLB" if ext == ".glb" else "GLTF_SEPARATE", "use_selection": True,
                  "export_animations": True, "export_skins": True, "export_morph": True,
                  "export_morph_animation": True, "export_force_sampling": True, "export_apply": False}
        props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
        bpy.ops.export_scene.gltf(filepath=str(out), **{k: v for k, v in wanted.items() if k in props})
    else:
        raise ValueError(f"Unsupported output format: {ext} (use .fbx or .glb)")


def main() -> None:
    a = args()
    bvh, character, out = Path(a["bvh"]), Path(a["character"]), Path(a["out"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tgt, objects = import_character(character)
    for o in objects:  # drop animation that came with the character
        for owner in (o, getattr(getattr(o, "data", None), "shape_keys", None)):
            if owner is not None and getattr(owner, "animation_data", None):
                owner.animation_data_clear()
    src, start, end = import_bvh(bvh)
    overrides = None
    if a.get("map") and a["map"] is not True:
        data = json.loads(Path(a["map"]).read_text(encoding="utf-8"))
        overrides = data.get("mapping", data) if isinstance(data, dict) else None
    source_names, target_names = [b.name for b in src.data.bones], [b.name for b in tgt.data.bones]
    mapping, unmapped = bone_map.auto_map(source_names, target_names, overrides)
    if not mapping:
        raise ValueError("No bones could be matched between the BVH and the character")
    threshold = float(a["align-threshold"]) if a.get("align-threshold") not in (None, True) else 15.0
    info = retarget(src, tgt, mapping, start, end, in_place=bool(a.get("in-place")), align_threshold=threshold,
                    foot_ik=not a.get("no-foot-ik"))
    meshes = [o for o in objects if o.type == "MESH"]
    result = {"ok": True, "armature": tgt.name, "bones": len(tgt.data.bones), "meshes": [m.name for m in meshes],
              "mapped": mapping, "unmapped": unmapped,
              "unmapped_source": [n for n in source_names if n not in mapping],
              "frames": [start, end], "fps": bpy.context.scene.render.fps / bpy.context.scene.render.fps_base,
              **info}
    if a.get("face") and a["face"] is not True:
        names, curves = apply_face(meshes, a["face"], start)
        result["face_matched"], result["face_curves"] = len(names), curves
    # remove the source skeleton and every action that is not on the character
    src_action = src.animation_data.action if src.animation_data else None
    src_data = src.data
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.data.armatures.remove(src_data)
    if src_action:
        bpy.data.actions.remove(src_action)
    used = {o.animation_data.action for o in objects if o.animation_data and o.animation_data.action}
    used |= {m.data.shape_keys.animation_data.action for m in meshes
             if m.data.shape_keys and m.data.shape_keys.animation_data and m.data.shape_keys.animation_data.action}
    for action in list(bpy.data.actions):
        if action not in used:
            bpy.data.actions.remove(action)
    export(out, objects, tgt)
    result["output"] = str(out)
    print("MOCAPGATE_RESULT " + json.dumps(result), flush=True)


try:
    main()
except Exception as exc:  # noqa: BLE001 — the caller reads the result line
    import traceback
    traceback.print_exc()
    print("MOCAPGATE_RESULT " + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)
    sys.exit(1)
