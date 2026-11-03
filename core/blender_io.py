"""MoCapGate — скрипт внутри Blender: BVH → сцена / FBX.

    blender -b --factory-startup -P core/blender_io.py -- --bvh take.bvh --fbx take.fbx --name take
    blender -P core/blender_io.py -- --bvh take.bvh --name take          (открыть в Blender с анимацией)

BVH MoCapGate — в сантиметрах, Y вверх; импорт со Scale 0.01 → метры, Z вверх в Blender.
FBX — оси для Maya/Unity/Unreal по умолчанию (Y вверх, −Z вперёд), только арматура с анимацией,
без «листовых» костей. Печатает MOCAPGATE_RESULT {json}.
"""
import json
import sys

import bpy  # type: ignore


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


def add_face(arm, csv_path, start):
    """Мимика: маленький меш FaceExpressions у кости головы с 52 shape keys ARKit и их анимацией.

    В FBX это blend shapes с кривыми — Unreal (Live Link / ARKit), Unity и Maya читают их по именам.
    Сам меш — служебный треугольник; кривые переносятся на лицо персонажа по именам.
    """
    import csv
    with open(csv_path, encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    names, rows = rows[0][2:], rows[1:]
    if not names or not rows:
        return None
    mesh = bpy.data.meshes.new("FaceExpressions")
    mesh.from_pydata([(0, 0, 0), (0.01, 0, 0), (0, 0.01, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("FaceExpressions", mesh)
    bpy.context.scene.collection.objects.link(obj)
    head = next((b.name for b in arm.data.bones if b.name.split(":")[-1] == "Head"), None)
    obj.parent = arm
    if head:
        obj.parent_type, obj.parent_bone = "BONE", head
    obj.shape_key_add(name="Basis", from_mix=False)
    for i, name in enumerate(names):
        key = obj.shape_key_add(name=name, from_mix=False)
        # у каждой формы своё крошечное смещение — пустые формы экспортёр FBX пропускает
        key.data[0].co = (0, 0, 0.001 * (i + 1))
    keys = mesh.shape_keys
    for name in names:  # первый ключ создаёт action и кривые одинаково в Blender 3.x–5.x
        keys.key_blocks[name].value = float(rows[0][names.index(name) + 2])
        keys.key_blocks[name].keyframe_insert("value", frame=start)
    action = keys.animation_data.action
    if hasattr(action, "fcurves"):
        fcurves = action.fcurves
    else:  # Blender 5: кривые в channelbag слота
        from bpy_extras import anim_utils
        fcurves = anim_utils.action_get_channelbag_for_slot(action, keys.animation_data.action_slot).fcurves
    action.name = "FaceExpressions"
    for i, name in enumerate(names):
        curve = fcurves.find(f'key_blocks["{name}"].value')
        curve.keyframe_points.add(len(rows) - 1)
        for k, row in enumerate(rows):
            point = curve.keyframe_points[k]
            point.co = point.handle_left = point.handle_right = (start + k, float(row[i + 2]))
            point.interpolation = "LINEAR"
        curve.update()
    return obj


def main() -> None:
    a = args()
    bvh, fbx, name = a["bvh"], a.get("fbx"), a.get("name") or "MoCapGate"
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    else:  # в открытом Blender — чистая сцена без куба, камеры и света
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    # Older BVH add-ons assign a float to render.fps; set rate ourselves, including fractional FPS.
    import re
    from pathlib import Path
    header = re.search(r"Frame Time:\s*([0-9.eE+-]+)", Path(bvh).read_text(encoding="utf-8"))
    if not header or float(header.group(1)) <= 0:
        raise ValueError("BVH frame time is missing or invalid")
    rate = 1.0 / float(header.group(1))
    scene = bpy.context.scene
    scene.render.fps = max(1, round(rate))
    scene.render.fps_base = scene.render.fps / rate
    bpy.ops.import_anim.bvh(filepath=bvh, global_scale=0.01, use_fps_scale=False, update_scene_fps=False,
                            update_scene_duration=True, rotate_mode="NATIVE", axis_forward="-Z", axis_up="Y")
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    arm.name = arm.data.name = name
    act = arm.animation_data.action if arm.animation_data else None
    sc = bpy.context.scene
    if act:
        act.name = name
        start, end = (int(v) for v in act.frame_range)
        sc.frame_start, sc.frame_end = start, end  # импорт BVH только удлиняет сцену, не укорачивает
    result = {"ok": True, "bones": len(arm.data.bones), "frames": [sc.frame_start, sc.frame_end],
              "fps": sc.render.fps}
    face = add_face(arm, a["face"], sc.frame_start) if a.get("face") else None
    if a.get("audio"):  # звук съёмки на таймлайне — синхронно с анимацией (кадр 1 = начало видео)
        try:
            sc.sequence_editor_create()
            strips = getattr(sc.sequence_editor, "strips", None) or sc.sequence_editor.sequences
            strips.new_sound("Audio", a["audio"], 1, sc.frame_start)
            result_audio = True
        except Exception as exc:  # noqa: BLE001 — без звука анимация всё равно открывается
            print("MoCapGate: audio skipped:", exc)
            result_audio = False
    else:
        result_audio = False
    if face:
        result["face_curves"] = len(face.data.shape_keys.key_blocks) - 1
    result["audio"] = result_audio
    if fbx:
        bpy.ops.object.select_all(action="DESELECT")
        arm.select_set(True)
        if face:
            face.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_simplify_factor=0.0, axis_forward="-Z", axis_up="Y",
                                 apply_unit_scale=True, armature_nodetype="NULL")
        result["fbx"] = fbx
    print("MOCAPGATE_RESULT " + json.dumps(result), flush=True)


main()
