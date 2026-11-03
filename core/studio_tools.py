"""MoCapGate — задачи Studio поверх готовой анимации: экспорт для движков, перенос на свой персонаж,
исправление кадров. Запускается как отдельный процесс (как clip_export), события — JSON-строки.

    python core/studio_tools.py engine  <take> <preset> <person|0> <all 0|1> <root_motion 0|1>
    python core/studio_tools.py retarget <take> <character file> <person|0> [<map.json>]
    python core/studio_tools.py repair  <take> <person|0> <first> <last>        (кадры с 1, включительно)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PRESETS = {"unreal": ".unreal.fbx", "unity": ".unity.fbx", "gltf": ".glb", "fbx": ".all.fbx", "livelink": ".livelink.csv",
           "mixamo": ".mixamo.fbx", "cascadeur": ".cascadeur.fbx", "blend": ".blend"}


def read_motion(path):
    """BVH → (корень Joint, кадры, шаг кадра) без потерь: имена как в файле (с mixamorig:), End Site,
    каналы позиции у любого сустава. character_rig.read_bvh для этого не годится — он убирает префикс."""
    import re
    from core.skeleton import Joint
    text = Path(path).read_text(encoding="utf-8")
    header, motion = text.split("MOTION", 1)
    tokens = re.findall(r"[{}]|[^\s{}]+", header)
    names, channels, nodes, stack, i = [], [], [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("ROOT", "JOINT"):
            node = Joint(tokens[i + 1], (0.0, 0.0, 0.0))
            if stack:
                stack[-1].children.append(node)
            nodes.append(node); names.append(node.name); channels.append([]); stack.append(node); i += 2
        elif tok == "End":  # End Site { OFFSET x y z }
            j = tokens.index("OFFSET", i)
            stack[-1].end_offset = tuple(float(v) for v in tokens[j + 1:j + 4])
            i = tokens.index("}", j) + 1
        elif tok == "OFFSET":
            stack[-1].offset = tuple(float(v) for v in tokens[i + 1:i + 4]); i += 4
        elif tok == "CHANNELS":
            n = int(tokens[i + 1]); channels[-1] = tokens[i + 2:i + 2 + n]; i += 2 + n
        elif tok == "}":
            stack.pop(); i += 1
        else:
            i += 1
    lines = motion.strip().splitlines()
    step = float(next(l for l in lines if l.startswith("Frame Time:")).split(":", 1)[1])
    start = next(k for k, l in enumerate(lines) if l.startswith("Frame Time:")) + 1
    rows = [[float(v) for v in l.split()] for l in lines[start:] if l.strip()]
    frames = []
    for row in rows:
        frame, cursor = {}, 0
        for name, cs in zip(names, channels):
            values = dict(zip(cs, row[cursor:cursor + len(cs)]))
            cursor += len(cs)
            frame[name] = {"rot": tuple(values.get(c, 0.0) for c in ("Zrotation", "Xrotation", "Yrotation"))}
            if "Xposition" in values:
                frame[name]["pos"] = tuple(values[c] for c in ("Xposition", "Yposition", "Zposition"))
        frames.append(frame)
    return nodes[0], frames, step


def selected_people(meta, person, everyone):
    from core import pipeline
    if everyone and meta.get("people"):
        return [pipeline.person_meta(meta, p["id"]) for p in meta["people"]]
    return [pipeline.person_meta(meta, person)]


def remember(take, person, key, value):
    """Записать результат в take.json — у участника или у дубля целиком."""
    from core import pipeline
    meta = pipeline.read_meta(take)
    target = next((p for p in meta.get("people", []) if p["id"] == person), None) if person else None
    # у участника — только его файлы; у дубля — общие (все участники) или единственного человека
    (target if target is not None else meta).setdefault(key, {}).update(value)
    pipeline.write_meta(take, meta)


def engine(take, preset, person, everyone, root_motion):
    from core import components, pipeline
    if preset not in PRESETS:
        raise ValueError("формат: " + " | ".join(PRESETS))
    meta = pipeline.read_meta(take)
    if meta.get("status") != "done":
        raise ValueError("Сначала обработайте дубль")
    people = selected_people(meta, person, everyone)
    many = everyone and len(people) > 1
    stem = pipeline.slug(meta["name"]) + "_all" if many else Path(people[0]["bvh"]).stem
    if preset == "livelink":  # мимика — всегда одного выбранного участника
        people = selected_people(meta, person, False)
        from core.livelink import write_livelink_csv
        source = people[0].get("face_file")
        if not source or not (take / source).is_file():
            raise ValueError("В дубле нет мимики: включите «Полное лицо и мимика» и обработайте заново")
        out = take / (Path(source).name.replace(".face.csv", "") + PRESETS[preset])
        write_livelink_csv(take / source, out, float(people[0].get("fps") or meta.get("fps") or 30))
        remember(take, person, "engine", {preset: out.name})
        pipeline.emit("done", "Live Link Face CSV готов", 1, file=out.name)
        return out
    blender = components.find_blender()
    if not blender:
        raise ValueError("Для экспорта нужен Blender — установите его в «Модели и инструменты»")
    from core.engine_export import command
    root_motion = root_motion and preset in ("unreal", "unity")  # glTF / FBX — без отдельной корневой кости
    out = take / (stem + PRESETS[preset])
    faces = [str(take / p["face_file"]) if p.get("face_file") and (take / p["face_file"]).is_file() else "-" for p in people]
    names = [f"{pipeline.slug(meta['name'])}_{p['id']}" if many else pipeline.slug(meta["name"]) for p in people]
    if preset == "unreal" and not many:
        names = ["Armature"]  # объект «Armature» Unreal не превращает в лишнюю верхнюю кость над root
    pipeline.emit("engine", f"Blender: {preset} · {len(people)} участн.…", 0.1, step="Экспорт для движка")
    # камера съёмки (матчмув) и звук (в .blend) — если есть; камера одна на сцену
    cam = people[0].get("camera_file") or meta.get("camera_file")
    cam = str(take / cam) if cam and (take / cam).is_file() else None
    audio = str(take / meta["audio"]) if preset == "blend" and meta.get("audio") and (take / meta["audio"]).is_file() else None
    code, lines = pipeline._run_streaming(command(blender, [str(take / p["bvh"]) for p in people], names, faces, preset,
                                                  str(out), root_motion, camera=cam, audio=audio), "engine")
    if code or not out.is_file():
        raise RuntimeError(pipeline.failure_summary("Blender", code, lines) if code else "Blender не создал файл")
    remember(take, None if many else person, "engine", {preset + ("_all" if many else ""): out.name})
    pipeline.emit("done", f"Готово: {out.name}", 1, file=out.name)
    return out


def retarget(take, character, person, mapping=None):
    from core import components, pipeline
    meta = pipeline.read_meta(take)
    if meta.get("status") != "done":
        raise ValueError("Сначала обработайте дубль")
    selected = pipeline.person_meta(meta, person)
    blender = components.find_blender()
    if not blender:
        raise ValueError("Для переноса на персонажа нужен Blender — установите его в «Модели и инструменты»")
    character = Path(character)
    if character.suffix.lower() not in (".fbx", ".glb", ".gltf", ".blend"):
        raise ValueError("Персонаж: файл .fbx, .glb, .gltf или .blend")
    out = take / (Path(selected["bvh"]).stem + "." + character.stem[:40].replace(" ", "_") + ".fbx")
    command = [blender, "-b", "--factory-startup", "-P", str(ROOT / "core" / "blender_retarget.py"), "--",
               "--bvh", str(take / selected["bvh"]), "--character", str(character), "--out", str(out)]
    if selected.get("face_file") and (take / selected["face_file"]).is_file():
        command += ["--face", str(take / selected["face_file"])]
    if mapping:
        command += ["--map", str(mapping)]
    pipeline.emit("retarget", f"Blender: переношу анимацию на {character.name}…", 0.1, step="Перенос на персонажа")
    code, lines = pipeline._run_streaming(command, "retarget")
    result = next((json.loads(l.split(" ", 1)[1]) for l in lines if l.startswith("MOCAPGATE_RESULT ")), {})
    if code or not out.is_file():
        raise RuntimeError(pipeline.failure_summary("Blender (персонаж)", code, lines) if code else "Blender не создал файл персонажа")
    remember(take, person, "retargeted", {character.name: out.name})
    missing = result.get("unmapped") or []
    pipeline.emit("done", f"Персонаж готов: {out.name}" + (f" · не найдены кости: {', '.join(missing[:6])}" if missing else ""), 1,
                  file=out.name, unmapped=missing)
    return out


def rewrite(take, person, change, note, done):
    """Изменить анимацию участника на месте: прежняя версия — в истории; BVH, сцена Maya, Man_Rig — заново,
    производные файлы (FBX, движки, персонажи) — устаревшими. change(root, frames, step) → frames."""
    from core import pipeline
    from core.anim_tools import write_bvh
    from core.bvh import save
    from core.maya_export import write as write_maya
    from core.take_history import snapshot
    meta = pipeline.read_meta(take)
    selected = pipeline.person_meta(meta, person)
    if meta.get("status") != "done" or not selected.get("bvh"):
        raise ValueError("Сначала обработайте дубль")
    bvh = take / selected["bvh"]
    root, frames, step = read_motion(bvh)
    frames = change(root, frames, step)
    pipeline.emit("history", "Сохраняю предыдущую версию анимации…", 0.1)
    try:
        snapshot(take, meta)
    except (OSError, ValueError, KeyError) as exc:  # как в process(): правка важнее неполной истории
        pipeline.emit("history", f"Предыдущую версию сохранить не удалось ({exc}); продолжаю")
    save(bvh, write_bvh(root, frames, step))  # иерархия как в исходном файле (mixamorig:, End Site)
    fps = 1 / step
    face = take / selected["face_file"] if selected.get("face_file") and (take / selected["face_file"]).is_file() else None
    if selected.get("maya_scene"):
        write_maya(take / selected["maya_scene"], root, frames, fps)
        if face:
            from core.face_export import append_csv_to_maya
            append_csv_to_maya(face, take / selected["maya_scene"])
    character = None
    if selected.get("character_scene"):  # Man_Rig — заново по новому BVH, иначе .ma и 3D показали бы старое
        from core import settings
        if settings.load().get("maya_rig") == "builtin":
            from core.character_rig import build
            pipeline.emit("character", "Переношу изменённое движение на Man_Rig…", 0.6)
            character = build(bvh, take / selected["character_scene"], fps)
            if face:
                from core.face_export import append_csv_to_maya
                append_csv_to_maya(face, take / character["character_scene"])
    meta = pipeline.read_meta(take)
    for entry in [meta] + meta.get("people", []):
        if entry.get("bvh") == selected["bvh"]:
            for stale in ("fbx", "engine", "retargeted"):
                entry.pop(stale, None)
            if character:
                entry.update(character)
            elif entry.get("character_scene"):
                for stale in ("character_scene", "character_motion", "maya_tools"):
                    entry.pop(stale, None)
            entry.setdefault("edits_log", []).append(note)
            if note.get("kind") == "repair":
                entry.setdefault("repairs", []).append(note["range"])
    pipeline.write_meta(take, meta)
    pipeline.attach_audio(take)
    pipeline.emit("done", done, 1)
    return bvh


def repair(take, person, first, last):
    """Заменить кадры first…last (с 1) плавной интерполяцией соседних."""
    from core.anim_tools import repair_range

    def change(root, frames, step):
        if type(first) is not int or type(last) is not int or not 1 <= first <= last <= len(frames):
            raise ValueError("Диапазон должен содержать целые кадры от 1 до конца дубля")
        return repair_range(root, frames, first - 1, last - 1)
    return rewrite(take, person, change, {"kind": "repair", "range": [first, last]},
                   f"Кадры {first}–{last} исправлены интерполяцией")


def edits_path(take, person):
    return Path(take) / f"edits-{person or 1}.json"


def bake(take, person):
    """Запечь несохранённый слой правок позы и ручные опоры стоп в анимацию; слой после этого пуст."""
    from core.pose_layer import apply_layer
    path = edits_path(take, person)
    if not path.is_file():
        raise ValueError("Нет несохранённых правок")
    data = json.loads(path.read_text(encoding="utf-8"))
    keys, contacts, pins = data.get("keys") or [], data.get("contacts") or {}, data.get("pins") or []
    if not keys and not contacts and not pins:
        raise ValueError("Нет несохранённых правок")

    def change(root, frames, step):
        frames = apply_layer(root, frames, keys) if keys else frames
        if pins:  # кисть/стопа — в точке на участке (IK); после ключей, до опор стоп
            from core.ik_pin import pins_apply
            from core import pipeline
            frames, infos = pins_apply(root, frames, 1 / step, pins)
            for info in infos:
                pipeline.emit("cleanup", f"{info['effector']}: отклонение до {info['max_error_cm']:.1f} см"
                              + (f", не дотягивается в {info['unreachable_frames']} кадрах" if info["unreachable_frames"] else ""), 0.3)
        if contacts:  # ручные участки опоры — поверх найденных автоматически
            from core.motion_cleanup import detect_contacts, foot_lock, merge_contacts
            final = merge_contacts(detect_contacts(root, frames, 1 / step), contacts.get("add"), contacts.get("remove"), len(frames))
            frames, info = foot_lock(root, frames, 1 / step, contacts=final)
            from core import pipeline
            pipeline.emit("cleanup", "стопы по разметке: скольжение " +
                          f"{max(info['slide_before'].values(), default=0):.1f} → {max(info['slide_after'].values(), default=0):.1f} см", 0.4)
        return frames
    marked = sum(len(r) for d in contacts.values() for r in d.values())
    out = rewrite(take, person, change, {"kind": "pose", "keys": len(keys), "contact_ranges": marked, "pins": len(pins)},
                  f"Правки применены: ключей {len(keys)}, закреплений {len(pins)}, участков опоры {marked}")
    path.unlink(missing_ok=True)
    return out


def main(argv):
    action, take = argv[0], Path(argv[1])
    if action == "engine":
        engine(take, argv[2], int(argv[3]) or None, argv[4] == "1", argv[5] == "1")
    elif action == "retarget":
        retarget(take, argv[2], int(argv[3]) or None, argv[4] if len(argv) > 4 else None)
    elif action == "repair":
        repair(take, int(argv[2]) or None, int(argv[3]), int(argv[4]))
    elif action == "bake":
        bake(take, int(argv[2]) or None)
    else:
        raise ValueError("действие: engine | retarget | repair | bake")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001 — причина должна дойти до окна
        from core.pipeline import emit
        emit("error", str(exc))
        raise SystemExit(1)
