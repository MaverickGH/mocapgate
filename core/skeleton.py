"""MoCapGate — гуманоидный скелет для BVH (иерархия суставов + оффсеты).

Оффсеты в сантиметрах, примерные пропорции взрослого человека. Этого достаточно
для валидного BVH, который открывают Blender и Maya; точные пропорции и ретаргет
на конкретный риг — на этапе доводки.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Joint:
    name: str
    offset: tuple[float, float, float]
    children: list["Joint"] = field(default_factory=list)
    end_offset: tuple[float, float, float] | None = None  # End Site для листьев


def humanoid() -> Joint:
    """Стандартный гуманоид: Hips → позвоночник/голова, руки, ноги."""
    def J(n, off, ch=None, end=None):
        return Joint(n, off, ch or [], end)
    return J("Hips", (0, 0, 0), [
        J("Spine", (0, 10, 0), [
            J("Spine1", (0, 12, 0), [
                J("Neck", (0, 14, 0), [
                    J("Head", (0, 6, 0), end=(0, 10, 0)),
                ]),
                J("LeftShoulder", (6, 12, 0), [
                    J("LeftArm", (13, 0, 0), [
                        J("LeftForeArm", (26, 0, 0), [
                            J("LeftHand", (24, 0, 0), end=(10, 0, 0)),
                        ]),
                    ]),
                ]),
                J("RightShoulder", (-6, 12, 0), [
                    J("RightArm", (-13, 0, 0), [
                        J("RightForeArm", (-26, 0, 0), [
                            J("RightHand", (-24, 0, 0), end=(-10, 0, 0)),
                        ]),
                    ]),
                ]),
            ]),
        ]),
        J("LeftUpLeg", (9, -2, 0), [
            J("LeftLeg", (0, -42, 0), [
                J("LeftFoot", (0, -42, 0), end=(0, -4, 14)),
            ]),
        ]),
        J("RightUpLeg", (-9, -2, 0), [
            J("RightLeg", (0, -42, 0), [
                J("RightFoot", (0, -42, 0), end=(0, -4, 14)),
            ]),
        ]),
    ])


def joint_names(root: Joint) -> list[str]:
    names: list[str] = []
    def walk(j: Joint):
        names.append(j.name)
        for c in j.children:
            walk(c)
    walk(root)
    return names
