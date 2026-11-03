"""MoCapGate — engine export presets (host side, stdlib only).

Builds the Blender command for core/blender_export.py and holds the bone-name mapping from
MoCapGate's Mixamo-style skeleton to the UE5 Mannequin (Manny) skeleton.

The Blender script imports this module from its own interpreter, so it must stay portable
source (no numpy, no native compilation) like the other Blender/worker entry points.

    from core import engine_export
    argv = engine_export.command(blender, ["a.bvh", "b.bvh"], ["alice", "bob"], ["a.face.csv", None],
                                 "unreal", "scene.fbx", root_motion=True)
    subprocess.run(argv)  # prints MOCAPGATE_RESULT {json}
"""
from __future__ import annotations
import json
import re
from pathlib import Path

PRESETS = ("unreal", "unity", "gltf", "fbx", "mixamo", "cascadeur", "blend")
EXTENSIONS = {"unreal": ".fbx", "unity": ".fbx", "gltf": ".glb", "fbx": ".fbx", "mixamo": ".fbx",
              "cascadeur": ".fbx", "blend": ".blend"}
MIXAMO_PREFIX = "mixamorig:"
SCRIPT = Path(__file__).resolve().with_name("blender_export.py")

# Mixamo-style names (without the mixamorig: prefix) → UE5 Mannequin names.
# Our spine has three joints (SMPL Spine/Spine1/Spine2; GEM-X Spine/Spine1/Spine2 after aliasing);
# Manny has five. The ends of the chain are kept semantically: Spine2 is the upper chest that carries
# the clavicles and neck, as spine_05 does on Manny; spine_02 and spine_04 do not exist in the export.
# The UE IK Retargeter maps chains by start/end bone, so a three-joint chain retargets cleanly.
UE5_NAMES: dict[str, str] = {
    "Hips": "pelvis",
    "Spine": "spine_01", "Spine1": "spine_03", "Spine2": "spine_05",
    "Neck": "neck_01", "Neck1": "neck_01", "Neck2": "neck_02", "Head": "head",
}
for _side, _s in (("Left", "l"), ("Right", "r")):
    UE5_NAMES.update({
        f"{_side}Shoulder": f"clavicle_{_s}", f"{_side}Arm": f"upperarm_{_s}",
        f"{_side}ForeArm": f"lowerarm_{_s}", f"{_side}Hand": f"hand_{_s}",
        f"{_side}UpLeg": f"thigh_{_s}", f"{_side}Leg": f"calf_{_s}", f"{_side}Foot": f"foot_{_s}",
        f"{_side}ToeBase": f"ball_{_s}", f"{_side}Toe": f"ball_{_s}",
    })
    for _finger, _ue in (("Thumb", "thumb"), ("Index", "index"), ("Middle", "middle"),
                         ("Ring", "ring"), ("Pinky", "pinky")):
        for _k in (1, 2, 3):
            UE5_NAMES[f"{_side}Hand{_finger}{_k}"] = f"{_ue}_0{_k}_{_s}"

# Twist joints (GEM-X/SOMA style names such as LeftArmTwist, LeftForeArmRoll2) → Manny twist bones.
_TWIST = re.compile(r"(Left|Right)(Arm|ForeArm|UpLeg|Leg)(?:Twist|Roll)_?(\d*)$")
_TWIST_BASE = {"Arm": "upperarm", "ForeArm": "lowerarm", "UpLeg": "thigh", "Leg": "calf"}


def base_name(name: str) -> str:
    """Strip a namespace prefix such as mixamorig:."""
    return name.rsplit(":", 1)[-1]


def ue_name(name: str) -> str:
    """UE5 Mannequin name for a MoCapGate joint; unknown joints keep their original (unprefixed) name."""
    base = base_name(name)
    if base in UE5_NAMES:
        return UE5_NAMES[base]
    twist = _TWIST.match(base)
    if twist:
        side, part, index = twist.groups()
        return f"{_TWIST_BASE[part]}_twist_{int(index or 1):02d}_{side[0].lower()}"
    return base


def unity_name(name: str) -> str:
    """Unity Humanoid auto-maps Mixamo names; the namespace prefix is removed."""
    return base_name(name)


def mixamo_name(name: str) -> str:
    """Mixamo download naming: every bone in the mixamorig: namespace."""
    return MIXAMO_PREFIX + base_name(name)


def cascadeur_name(name: str) -> str:
    """Cascadeur's Mixamo auto-rig mapping expects Mixamo names without the namespace."""
    return base_name(name)


def participant_names(bvhs, names) -> list[str]:
    """One name per BVH: given names, one name numbered for several takes, or the BVH stems."""
    bvhs, names = list(bvhs), [n for n in (names or []) if n]
    if len(names) == len(bvhs):
        return names
    if len(names) == 1:
        return names if len(bvhs) == 1 else [f"{names[0]}_{i + 1}" for i in range(len(bvhs))]
    if names:
        raise ValueError("give one name or one name per BVH")
    return [Path(b).stem for b in bvhs]


def command(blender, bvhs, names=None, faces=None, preset="fbx", out=None, root_motion=False,
            camera=None, audio=None) -> list[str]:
    """argv for `blender -b --factory-startup -P core/blender_export.py -- ...`.

    camera — a mocapgate.camera/1 JSON (core/camera_export.py) added as a Camera object to every preset;
    audio — a sound file added as a sequencer strip at the first frame (only the blend preset keeps it).
    """
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; expected one of {', '.join(PRESETS)}")
    bvhs = [str(b) for b in bvhs]
    if not bvhs:
        raise ValueError("at least one BVH is required")
    if not out:
        raise ValueError("output path is required")
    faces = list(faces or [])
    if faces and len(faces) != len(bvhs):
        raise ValueError("--face must be given once per BVH (use None for none)")
    argv = [str(blender), "-b", "--factory-startup", "-P", str(SCRIPT), "--",
            "--preset", preset, "--out", str(out)]
    for i, (bvh, name) in enumerate(zip(bvhs, participant_names(bvhs, names))):
        argv += ["--bvh", bvh, "--name", name]
        if faces:
            argv += ["--face", str(faces[i]) if faces[i] else "-"]
    if root_motion:
        argv.append("--root-motion")
    if camera:
        argv += ["--camera", str(camera)]
    if audio:
        argv += ["--audio", str(audio)]
    return argv


def parse_result(stdout: str) -> dict | None:
    """The MOCAPGATE_RESULT json printed by the Blender script, or None."""
    for line in reversed(stdout.splitlines()):
        if line.startswith("MOCAPGATE_RESULT "):
            return json.loads(line[len("MOCAPGATE_RESULT "):])
    return None
