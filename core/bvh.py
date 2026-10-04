"""MoCapGate — запись BVH (универсальный формат мокапа для Blender и Maya).

Строит секцию HIERARCHY из скелета и MOTION из списка кадров. Корень несёт
позицию+поворот (6 каналов), остальные суставы — поворот (3 канала, порядок ZXY).
Кадр: {"Hips": {"pos": (x,y,z), "rot": (z,x,y)}, "<joint>": {"rot": (z,x,y)}}.
Отсутствующие повороты считаются нулевыми.
"""
from __future__ import annotations
from core.skeleton import Joint

_ROT = ("Zrotation", "Xrotation", "Yrotation")
_POS = ("Xposition", "Yposition", "Zposition")


def _hierarchy(root: Joint) -> tuple[list[str], list[tuple[str, str]]]:
    lines: list[str] = ["HIERARCHY"]
    channels: list[tuple[str, str]] = []

    def fmt(off):
        return f"{off[0]:g} {off[1]:g} {off[2]:g}"

    def walk(j: Joint, depth: int, is_root: bool):
        pad = "  " * depth
        tag = "ROOT" if is_root else "JOINT"
        lines.append(f"{pad}{tag} {j.name}")
        lines.append(f"{pad}{{")
        lines.append(f"{pad}  OFFSET {fmt(j.offset)}")
        if is_root:
            lines.append(f"{pad}  CHANNELS 6 {' '.join(_POS + _ROT)}")
            channels.extend((j.name, c) for c in _POS + _ROT)
        else:
            lines.append(f"{pad}  CHANNELS 3 {' '.join(_ROT)}")
            channels.extend((j.name, c) for c in _ROT)
        for c in j.children:
            walk(c, depth + 1, False)
        if j.end_offset is not None:
            lines.append(f"{pad}  End Site")
            lines.append(f"{pad}  {{")
            lines.append(f"{pad}    OFFSET {fmt(j.end_offset)}")
            lines.append(f"{pad}  }}")
        lines.append(f"{pad}}}")

    walk(root, 0, True)
    return lines, channels


def write(root: Joint, frames: list[dict], frame_time: float = 1 / 30) -> str:
    lines, channels = _hierarchy(root)
    out = list(lines)
    out.append("MOTION")
    out.append(f"Frames: {len(frames)}")
    out.append(f"Frame Time: {frame_time:.7f}")
    for fr in frames:
        row: list[str] = []
        for joint, chan in channels:
            data = fr.get(joint, {})
            if chan in _POS:
                i = _POS.index(chan)
                row.append(f"{data.get('pos', (0, 0, 0))[i]:.4f}")
            else:
                i = _ROT.index(chan)
                row.append(f"{data.get('rot', (0, 0, 0))[i]:.4f}")
        out.append(" ".join(row))
    return "\n".join(out) + "\n"


def save(path, text: str) -> None:
    """Записать BVH с переводами строк LF на любой ОС (на Windows write_text дал бы CRLF)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
