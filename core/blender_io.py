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
    if fbx:
        bpy.ops.object.select_all(action="DESELECT")
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"ARMATURE"}, add_leaf_bones=False,
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_simplify_factor=0.0, axis_forward="-Z", axis_up="Y",
                                 apply_unit_scale=True, armature_nodetype="NULL")
        result["fbx"] = fbx
    print("MOCAPGATE_RESULT " + json.dumps(result), flush=True)


main()
