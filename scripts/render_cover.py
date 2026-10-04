"""Обложка программы MoCapGate для сайта: 1600×900, та же сцена, что у иконки, без плашки и текста.

    blender -b --factory-startup -P scripts/render_cover.py -- docs/site/mocapgate-cover-blender.png
    python -c "from PIL import Image; Image.open('docs/site/mocapgate-cover-blender.png').convert('RGB').save('docs/site/mocapgate-cover-blender.webp', quality=88)"

Поза скелета считается нашим же FK SMPL (core/smpl.py) — бег, шаг из портала.
"""
import math
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Vector  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import smpl  # noqa: E402
from core.rotations import axis_angle_to_matrix, matmul, matrix_to_axis_angle  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else str(ROOT / "docs/site/mocapgate-cover-blender.png")

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.use_bloom = True
sc.eevee.bloom_intensity = 0.04
sc.eevee.bloom_radius = 5.0
sc.eevee.use_gtao = True
sc.eevee.taa_render_samples = 64
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.render.film_transparent = False
sc.view_settings.view_transform = "Filmic"
sc.view_settings.look = "Medium High Contrast"


def material(name, color, metallic=0.0, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


plate_m = material("plate", (0.035, 0.11, 0.115), rough=0.35)
metal_m = material("metal", (0.42, 0.45, 0.47), metallic=0.85, rough=0.38)
glow_m = material("glow", (0.3, 1.0, 0.95), emit=(0.25, 0.95, 0.9), strength=3.0)
bone_m = material("bone", (0.62, 0.66, 0.68), metallic=0.6, rough=0.3)
joint_m = material("joint", (1.0, 0.45, 0.12), emit=(1.0, 0.4, 0.08), strength=1.6)

# фон — большая тёмная плоскость с мягким бирюзовым светом из портала
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.45))
bpy.context.object.data.materials.append(plate_m)

# портал: П-образная рама слева, светящаяся кромка внутри
def box(loc, size, mat, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = size
    if bevel:
        m = o.modifiers.new("b", "BEVEL")
        m.width, m.segments = bevel, 3
    o.data.materials.append(mat)
    return o


for loc, size in (((-1.22, 0.0, 0.25), (0.26, 2.3, 0.5)), ((-0.62, 1.03, 0.25), (1.45, 0.26, 0.5)),
                  ((-0.62, -1.03, 0.25), (1.45, 0.26, 0.5))):
    box(loc, size, metal_m)
for loc, size in (((-1.06, 0.0, 0.3), (0.05, 1.82, 0.42)), ((-0.62, 0.875, 0.3), (0.84, 0.05, 0.42)),
                  ((-0.62, -0.875, 0.3), (0.84, 0.05, 0.42))):
    box(loc, size, glow_m, bevel=0)

# бегущий скелет из нашего FK (SMPL): лицом вправо (+X), шаг из портала
pose = [0.0] * 63


def setj(j, v):
    pose[3 * (j - 1):3 * j] = v


def compose(*rvs):
    m = axis_angle_to_matrix([0, 0, 0])
    for rv in rvs:
        m = matmul(m, axis_angle_to_matrix(rv))
    return matrix_to_axis_angle(m)


setj(1, [-1.15, 0, 0.08]); setj(4, [0.9, 0, 0])      # левое бедро вперёд, колено слегка
setj(2, [0.55, 0, -0.05]); setj(5, [1.9, 0, 0])      # правое назад, пятка к ягодице
setj(7, [0.2, 0, 0]); setj(8, [0.5, 0, 0])
setj(3, [0.12, 0, 0]); setj(6, [0.06, 0, 0])         # корпус наклонён вперёд
setj(16, compose([0.75, 0, 0], [0, 0, -1.3])); setj(18, [0, -1.45, 0])   # левая рука назад, локоть 85°
setj(17, compose([-0.85, 0, 0], [0, 0, 1.3])); setj(19, [0, 1.45, 0])    # правая вперёд
setj(15, [-0.1, 0, 0])
P = smpl.fk([0, math.radians(90), 0], pose, [0, 0, 0])
s = 1.3
pts = [Vector((p[0] * s + 0.55, p[1] * s + 0.25, p[2] * s + 0.7)) for p in P]

def cyl(a, b, r, mat):
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(a + b) / 2, vertices=24)
    o = bpy.context.object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()

for j, par in enumerate(smpl.PARENTS):
    if par >= 0:
        cyl(pts[par], pts[j], 0.045, bone_m)
for j, p in enumerate(pts):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.075 if j != 15 else 0.16, location=p, segments=24, ring_count=12)
    bpy.context.object.data.materials.append(joint_m if j != 15 else bone_m)
    bpy.ops.object.shade_smooth()

# след движения — светящиеся дуги за скелетом
for k, (y, ln) in enumerate(((0.55, 0.7), (0.15, 0.95), (-0.25, 0.6))):
    box((-0.25 - ln / 2 + 0.1, y, 0.62), (ln, 0.025, 0.025), glow_m, bevel=0)

# свет и камера
bpy.ops.object.light_add(type="AREA", location=(2.5, 2.0, 4.0))
bpy.context.object.data.energy, bpy.context.object.data.size = 350, 3
bpy.ops.object.light_add(type="POINT", location=(2.2, -0.6, 1.5))
bpy.context.object.data.energy, bpy.context.object.data.color = 120, (1.0, 0.55, 0.25)
bpy.ops.object.light_add(type="POINT", location=(-0.9, 0.0, 1.2))
bpy.context.object.data.energy, bpy.context.object.data.color = 60, (0.3, 1.0, 0.95)
bpy.ops.object.camera_add(location=(-0.1, -0.05, 9.0), rotation=(0, 0, 0))
cam = bpy.context.object
cam.data.type = "ORTHO"
cam.data.ortho_scale = 6.2
sc.camera = cam
sc.world = bpy.data.worlds.new("w")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.03, 0.035, 1)
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("COVER", OUT)
