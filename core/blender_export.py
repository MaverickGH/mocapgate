"""MoCapGate — engine export presets inside Blender: BVH (one or several participants) → FBX / GLB.

    blender -b --factory-startup -P core/blender_export.py -- --preset unreal --out scene.fbx \
        --bvh alice.bvh --name alice --face alice.face.csv \
        --bvh bob.bvh --name bob --face - [--root-motion]

Presets
    unreal  FBX for UE5: bones renamed to the UE5 Mannequin (pelvis, spine_01.., thigh_l..), a `root` bone at
            the origin above pelvis. Centimetres: the scene works in BVH centimetres with a 1 cm unit, so the FBX
            stores cm values, UnitScaleFactor 1 and no 100x node scale. Y up / -Z forward, no leaf bones.
    unity   FBX for Unity Humanoid: Mixamo names without namespace, Y up, scale baked into the transforms
            (FBX_SCALE_ALL) so objects import at scale 1; with --root-motion a `Root` bone above Hips.
    gltf    GLB (Y up, metres) with skeletal and shape-key (morph weight) animation.
    fbx     plain FBX as core/blender_io.py, several participants in one scene.
    mixamo  FBX like a Mixamo download: bones in the `mixamorig:` namespace, centimetres (UnitScaleFactor 1, no node
            scale), Y up / -Z forward; a single armature is named "Armature" (several keep participant names).
    cascadeur  FBX for Cascadeur: Mixamo names without the namespace, centimetres as mixamo.
    blend   a .blend file (metres): every armature with its action named per participant, face meshes, camera and
            the audio strip; saved without relative path remapping.

Several --bvh give one armature per participant named by --name; BVH root positions already place people in a
shared space, so every armature stays at the origin and keeps its own placement. --face (aligned with --bvh,
"-" for none) adds a FaceExpressions mesh with ARKit shape keys parented to the head bone.
--root-motion (unreal/unity): horizontal translation and yaw of the pelvis move to the root bone; the pelvis keeps
height, tilt and the remainder.
--camera camera.json (mocapgate.camera/1, core/camera_export.py): a static Camera object (lens from focal_mm with a
36 mm horizontal sensor, render resolution and principal-point shift); Y-up metres map to Blender exactly as the BVH
import does (axis_forward -Z, axis_up Y). Exported with every preset.
--audio file: blend only — a sound strip in the sequencer at the first frame; FBX/GLB report "audio": false.
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
from core.engine_export import (PRESETS, base_name, cascadeur_name, mixamo_name, participant_names,  # noqa: E402
                                 ue_name, unity_name)

CENTIMETRE_PRESETS = ("unreal", "mixamo", "cascadeur")  # scene in BVH centimetres with a 1 cm unit


def parse(argv) -> dict:
    out = {"bvh": [], "name": [], "face": [], "preset": "fbx", "out": None, "root_motion": False,
           "camera": None, "audio": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root-motion":
            out["root_motion"], i = True, i + 1
        elif a in ("--bvh", "--name", "--face", "--preset", "--out", "--camera", "--audio") and i + 1 < len(argv):
            key, value = a[2:], argv[i + 1]
            if isinstance(out[key], list):
                out[key].append(value)
            else:
                out[key] = value
            i += 2
        else:
            raise SystemExit(f"unexpected argument {a!r}")
    if out["preset"] not in PRESETS:
        raise SystemExit(f"unknown preset {out['preset']!r}")
    if not out["bvh"] or not out["out"]:
        raise SystemExit("--bvh and --out are required")
    if out["face"] and len(out["face"]) != len(out["bvh"]):
        raise SystemExit("--face must be given once per --bvh ('-' for none)")
    return out


def fcurves_of(action, slot=None):
    if hasattr(action, "fcurves"):
        return action.fcurves
    from bpy_extras import anim_utils  # Blender 5: curves live in the slot's channelbag
    return anim_utils.action_get_channelbag_for_slot(action, slot).fcurves


def set_rate(bvh) -> None:
    header = re.search(r"Frame Time:\s*([0-9.eE+-]+)", Path(bvh).read_text(encoding="utf-8"))
    if not header or float(header.group(1)) <= 0:
        raise ValueError(f"BVH frame time is missing or invalid: {bvh}")
    rate = 1.0 / float(header.group(1))
    scene = bpy.context.scene
    scene.render.fps = max(1, round(rate))
    scene.render.fps_base = scene.render.fps / rate


def import_bvh(path, name, unit):
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=path, global_scale=unit, use_fps_scale=False, update_scene_fps=False,
                            update_scene_duration=True, rotate_mode="NATIVE", axis_forward="-Z", axis_up="Y")
    arm = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
    arm.name = arm.data.name = name
    if arm.animation_data and arm.animation_data.action:
        arm.animation_data.action.name = name
    return arm


def rename_bones(arm, rule) -> None:
    """Rename via RNA so Blender fixes the action's data paths; name clashes keep the original name."""
    taken = {b.name for b in arm.data.bones}
    for bone in list(arm.data.bones):
        new = rule(bone.name)
        if new != bone.name and new not in taken:
            taken.discard(bone.name)
            bone.name = new
            taken.add(new)


def hips_bone(arm):
    names = {base_name(b.name): b.name for b in arm.data.bones}
    for candidate in ("pelvis", "Hips"):
        if candidate in names:
            return names[candidate]
    return next(b.name for b in arm.data.bones if b.parent is None)


def head_bone(arm):
    return next((b.name for b in arm.data.bones if base_name(b.name).lower() == "head"), None)


def frame_range(arm):
    act = arm.animation_data.action if arm.animation_data else None
    if not act:
        return bpy.context.scene.frame_start, bpy.context.scene.frame_end
    start, end = (int(round(v)) for v in act.frame_range)
    return start, end


def sample(arms_bones, frames):
    """Armature-space matrices of the given pose bones for every frame (one scene evaluation per frame)."""
    tracks = {key: [] for key in arms_bones}
    scene = bpy.context.scene
    for f in frames:
        scene.frame_set(f)
        for arm, bone in arms_bones:
            tracks[(arm, bone)].append(arm.pose.bones[bone].matrix.copy())
    return tracks


def add_root(arm, root, hips, length) -> None:
    """Root bone at the origin with identity rest (tail along +Y), parent of the pelvis."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    bones = arm.data.edit_bones
    bone = bones.new(root)
    bone.head, bone.tail, bone.roll = (0.0, 0.0, 0.0), (0.0, length, 0.0), 0.0
    bones[hips].parent = bone
    bones[hips].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.pose.bones[root].rotation_mode = "QUATERNION"


def key_basis(pose_bone, basis, frame, previous):
    """Write a local (basis) matrix as keys in the bone's own rotation mode; returns the rotation used."""
    loc, rot, _ = basis.decompose()
    pose_bone.location = loc
    pose_bone.keyframe_insert("location", frame=frame, group=pose_bone.name)
    mode = pose_bone.rotation_mode
    if mode == "QUATERNION":
        if previous is not None:
            rot.make_compatible(previous)
        pose_bone.rotation_quaternion = rot
        pose_bone.keyframe_insert("rotation_quaternion", frame=frame, group=pose_bone.name)
        return rot
    if mode == "AXIS_ANGLE":
        axis, angle = rot.to_axis_angle()
        pose_bone.rotation_axis_angle = (angle, *axis)
        pose_bone.keyframe_insert("rotation_axis_angle", frame=frame, group=pose_bone.name)
        return rot
    euler = basis.to_3x3().to_euler(mode, previous) if previous is not None else basis.to_3x3().to_euler(mode)
    pose_bone.rotation_euler = euler
    pose_bone.keyframe_insert("rotation_euler", frame=frame, group=pose_bone.name)
    return euler


def root_motion(arm, root, hips, frames, track) -> None:
    """Pelvis ground-plane translation (Blender X/Y, Z up) and yaw → root; pelvis keeps the remainder."""
    rest_root = arm.data.bones[root].matrix_local.copy()
    rest_hips = arm.data.bones[hips].matrix_local.copy()
    relative = rest_root.inverted() @ rest_hips
    delta_rest = rest_hips.to_3x3().inverted()
    proot, phips = arm.pose.bones[root], arm.pose.bones[hips]
    prev_yaw, prev_root, prev_hips = None, None, None
    for f, m in zip(frames, track):
        q = (m.to_3x3() @ delta_rest).to_quaternion()  # pelvis rotation relative to rest, armature space
        yaw = 2.0 * math.atan2(q.z, q.w)  # twist about the vertical axis
        if prev_yaw is not None:
            yaw += 2.0 * math.pi * round((prev_yaw - yaw) / (2.0 * math.pi))
        prev_yaw = yaw
        t = m.to_translation()
        m_root = Matrix.Translation((t.x, t.y, 0.0)) @ Matrix.Rotation(yaw, 4, "Z")
        prev_root = key_basis(proot, rest_root.inverted() @ m_root, f, prev_root)
        prev_hips = key_basis(phips, relative.inverted() @ m_root.inverted() @ m, f, prev_hips)
    for pb in (proot, phips):
        for curve in fcurves_of(arm.animation_data.action, getattr(arm.animation_data, "action_slot", None)):
            if curve.data_path.startswith(f'pose.bones["{pb.name}"]'):
                for point in curve.keyframe_points:
                    point.interpolation = "LINEAR"


def add_face(arm, csv_path, start, name, size):
    """FaceExpressions helper mesh on the head bone with animated ARKit shape keys (logic of core/blender_io.py)."""
    import csv
    with open(csv_path, encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    names, rows = rows[0][2:], [r for r in rows[1:] if r]
    if not names or not rows:
        return None
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (size, 0, 0), (0, size, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = arm
    head = head_bone(arm)
    if head:
        obj.parent_type, obj.parent_bone = "BONE", head
    obj.shape_key_add(name="Basis", from_mix=False)
    for i, key_name in enumerate(names):
        key = obj.shape_key_add(name=key_name, from_mix=False)
        key.data[0].co = (0, 0, 0.1 * size * (i + 1))  # empty shapes are dropped by the FBX exporter
    keys = mesh.shape_keys
    for i, key_name in enumerate(names):
        keys.key_blocks[key_name].value = float(rows[0][i + 2])
        keys.key_blocks[key_name].keyframe_insert("value", frame=start)
    action = keys.animation_data.action
    action.name = name
    curves = fcurves_of(action, getattr(keys.animation_data, "action_slot", None))
    for i, key_name in enumerate(names):
        curve = curves.find(f'key_blocks["{key_name}"].value')
        curve.keyframe_points.add(len(rows) - 1)
        for k, row in enumerate(rows):
            point = curve.keyframe_points[k]
            point.co = point.handle_left = point.handle_right = (start + k, float(row[i + 2]))
            point.interpolation = "LINEAR"
        curve.update()
    return obj


def add_camera(path, unit):
    """Static camera from a mocapgate.camera/1 JSON: Y-up metres → Blender Z-up scene units, GL camera axes."""
    from bpy_extras.io_utils import axis_conversion
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "mocapgate.camera/1":
        raise ValueError(f"not a mocapgate.camera/1 file: {path}")
    scene = bpy.context.scene
    cam = bpy.data.cameras.new("Camera")
    obj = bpy.data.objects.new("Camera", cam)
    scene.collection.objects.link(obj)
    width, height = int(data["width"]), int(data["height"])
    cam.sensor_fit, cam.sensor_width = "HORIZONTAL", float(data.get("sensor_width_mm", 36.0))
    cam.lens = float(data["focal_mm"])
    cx, cy = data.get("principal_point") or (width / 2.0, height / 2.0)
    cam.shift_x, cam.shift_y = (width / 2.0 - cx) / width, (cy - height / 2.0) / width
    metres = 100.0 * unit  # scene units per metre: 1 (metres) or 100 (centimetre presets)
    cam.clip_start, cam.clip_end = 0.05 * metres, 1000.0 * metres
    local = Matrix.Translation(Vector(data["position"]) * metres) @ Quaternion(data["rotation_quat"]).to_matrix().to_4x4()
    obj.matrix_world = axis_conversion(from_forward="-Z", from_up="Y").to_4x4() @ local
    scene.camera = obj
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
    return obj


def add_audio(path) -> bool:
    """Sound strip at the first frame (sequencer API: `sequences` before Blender 4.4, `strips` from 4.4/5.x)."""
    scene = bpy.context.scene
    editor = scene.sequence_editor or scene.sequence_editor_create()
    strips = editor.strips if hasattr(editor, "strips") else editor.sequences
    strips.new_sound(Path(path).stem or "Audio", str(Path(path).resolve()), 1, scene.frame_start)
    return True


def export(preset, out, objects, active, camera=None) -> None:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if preset == "blend":
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(out).resolve()), check_existing=False, relative_remap=False)
        return
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
    if preset == "gltf":
        props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
        wanted = {"export_format": "GLB", "use_selection": True, "export_animations": True, "export_morph": True,
                  "export_morph_animation": True, "export_skins": True, "export_force_sampling": True,
                  "export_animation_mode": "ACTIONS", "export_nla_strips": True, "export_yup": True,
                  "export_def_bones": False, "export_apply": False, "export_cameras": camera is not None}
        bpy.ops.export_scene.gltf(filepath=out, **{k: v for k, v in wanted.items() if k in props})
        return
    scale = {"unity": "FBX_SCALE_ALL"}.get(preset, "FBX_SCALE_NONE")
    types = {"ARMATURE", "MESH"} | ({"CAMERA"} if camera is not None else set())
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types=types, add_leaf_bones=False,
                             bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                             bake_anim_simplify_factor=0.0, axis_forward="-Z", axis_up="Y",
                             apply_unit_scale=True, apply_scale_options=scale, armature_nodetype="NULL")


def main() -> None:
    a = parse(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    preset, out = a["preset"], a["out"]
    names = participant_names(a["bvh"], a["name"])
    faces = a["face"] or ["-"] * len(a["bvh"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    set_rate(a["bvh"][0])
    scene = bpy.context.scene
    # Unreal: keep BVH centimetres as raw values with a 1 cm scene unit, so the FBX carries centimetres with
    # UnitScaleFactor 1 and no 100x scale on the armature node. Other presets work in metres.
    unit = 1.0 if preset in CENTIMETRE_PRESETS else 0.01
    if preset in CENTIMETRE_PRESETS:
        scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 0.01
    arms = [import_bvh(path, name, unit) for path, name in zip(a["bvh"], names)]
    ranges = [frame_range(arm) for arm in arms]
    scene.frame_start, scene.frame_end = min(r[0] for r in ranges), max(r[1] for r in ranges)

    rule = {"unreal": ue_name, "unity": unity_name, "mixamo": mixamo_name, "cascadeur": cascadeur_name}.get(preset)
    if rule:
        for arm in arms:
            rename_bones(arm, rule)
    if preset == "mixamo" and len(arms) == 1:  # Mixamo downloads: the armature node is "Armature"
        arms[0].name = arms[0].data.name = "Armature"
    root_name = {"unreal": "root", "unity": "Root"}.get(preset)
    want_root = preset == "unreal" or (preset == "unity" and a["root_motion"])
    moving = a["root_motion"] and want_root
    hips = {arm: hips_bone(arm) for arm in arms}
    tracks = {}
    if moving:
        frames = list(range(scene.frame_start, scene.frame_end + 1))
        tracks = sample([(arm, hips[arm]) for arm in arms], frames)
    if want_root:
        for arm, (start, end) in zip(arms, ranges):
            add_root(arm, root_name, hips[arm], 10.0 * unit)
            if moving:
                track = tracks[(arm, hips[arm])][start - scene.frame_start:end - scene.frame_start + 1]
                root_motion(arm, root_name, hips[arm], list(range(start, end + 1)), track)
        scene.frame_set(scene.frame_start)

    several = len(arms) > 1
    face_objs, face_curves = [], 0
    for arm, csv_path, (start, _), name in zip(arms, faces, ranges, names):
        if csv_path and csv_path != "-":
            obj = add_face(arm, csv_path, start, f"{name}_FaceExpressions" if several else "FaceExpressions", unit)
            if obj:
                face_objs.append(obj)
                face_curves += len(obj.data.shape_keys.key_blocks) - 1

    camera = add_camera(a["camera"], unit) if a["camera"] else None
    audio = add_audio(a["audio"]) if a["audio"] and preset == "blend" else False
    export(preset, out, arms + face_objs + ([camera] if camera else []), arms[0], camera)
    result = {"ok": True, "preset": preset, "out": out, "armatures": len(arms), "names": names,
              "bones": sum(len(arm.data.bones) for arm in arms), "bones_per_armature": [len(arm.data.bones) for arm in arms],
              "frames": [scene.frame_start, scene.frame_end], "frame_count": scene.frame_end - scene.frame_start + 1,
              "fps": scene.render.fps / scene.render.fps_base, "face_curves": face_curves,
              "root_motion": moving, "root": root_name if want_root else None,
              "armature_names": [arm.name for arm in arms], "camera": camera.name if camera else None,
              "lens": camera.data.lens if camera else None, "audio": audio,
              "blender": bpy.app.version_string}
    print("MOCAPGATE_RESULT " + json.dumps(result), flush=True)


main()
