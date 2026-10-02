"""Einfache Figur mit Skelett (Armature), die Anlauf nimmt, springt und landet.

Aufruf:  python3 scripts/figur_sprung.py
(lokal alternativ: blender --background --python scripts/figur_sprung.py)

Ergebnis: renders/figur_sprung.gif und renders/figur_sprung.blend
"""
import math
import os
import subprocess

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(ROOT, "renders", "frames", "figur_sprung")
GIF_PATH = os.path.join(ROOT, "renders", "figur_sprung.gif")
BLEND_PATH = os.path.join(ROOT, "renders", "figur_sprung.blend")

FPS = 24
FRAME_END = 64
TAKEOFF, LANDING = 16, 34  # Absprung- und Lande-Frame
JUMP_HEIGHT = 1.0
JUMP_DISTANCE = 1.6  # Figur blickt nach -Y und springt in diese Richtung

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, FRAME_END


# --- Skelett ---------------------------------------------------------------

arm_data = bpy.data.armatures.new("Skelett")
rig = bpy.data.objects.new("Figur", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")


def bone(name, head, tail, parent=None, connect=False):
    b = arm_data.edit_bones.new(name)
    b.head, b.tail = head, tail
    if parent:
        b.parent = arm_data.edit_bones[parent]
        b.use_connect = connect
    return b


bone("root", (0, 0, 0), (0, 0.3, 0))
bone("hips", (0, 0, 1.0), (0, 0, 1.1), "root")
bone("spine", (0, 0, 1.1), (0, 0, 1.62), "hips", connect=True)
bone("head", (0, 0, 1.62), (0, 0, 2.0), "spine", connect=True)
for side, x in (("L", 0.27), ("R", -0.27)):
    bone(f"upperarm.{side}", (x, 0, 1.56), (x, 0, 1.28), "spine")
    bone(f"forearm.{side}", (x, 0, 1.28), (x, 0, 1.0), f"upperarm.{side}", connect=True)
    lx = x * 0.45
    # Knie leicht nach vorn (-Y) geknickt, damit IK die Beine richtig beugt.
    bone(f"thigh.{side}", (lx, 0, 1.0), (lx, -0.06, 0.53), "hips")
    bone(f"shin.{side}", (lx, -0.06, 0.53), (lx, 0, 0.08), f"thigh.{side}", connect=True)
    bone(f"foot.{side}", (lx, 0, 0.08), (lx, -0.2, 0.08), "root")

bpy.ops.object.mode_set(mode="POSE")
for side in ("L", "R"):
    ik = rig.pose.bones[f"shin.{side}"].constraints.new("IK")
    ik.target, ik.subtarget, ik.chain_count = rig, f"foot.{side}", 2
for pb in rig.pose.bones:
    pb.rotation_mode = "QUATERNION"
bpy.ops.object.mode_set(mode="OBJECT")


# --- Körperteile (an Knochen gehängt) ---------------------------------------

def material(name, rgb, roughness=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    return m


SKIN = material("Haut", (0.85, 0.6, 0.45))
SHIRT = material("Shirt", (0.1, 0.35, 0.75))
PANTS = material("Hose", (0.15, 0.15, 0.2))
SHOES = material("Schuhe", (0.8, 0.2, 0.1))


def attach(obj, bone_name, mat):
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    world = obj.matrix_world.copy()
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    bpy.context.view_layer.update()
    obj.matrix_world = world


def limb(bone_name, radius, mat):
    """Zylinder entlang eines Knochens, mit Kugeln als Gelenke an den Enden."""
    b = arm_data.bones[bone_name]
    head, tail = b.head_local, b.tail_local
    direction = tail - head
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=direction.length, location=(head + tail) / 2,
        rotation=direction.to_track_quat("Z", "Y").to_euler(), vertices=24)
    attach(bpy.context.object, bone_name, mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=tail, segments=24, ring_count=12)
    attach(bpy.context.object, bone_name, mat)


bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 1.33), segments=32, ring_count=16)
bpy.context.object.scale = (0.26, 0.17, 0.36)
attach(bpy.context.object, "spine", SHIRT)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.17, location=(0, 0, 1.85), segments=32, ring_count=16)
attach(bpy.context.object, "head", SKIN)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 1.02), segments=24, ring_count=12)
bpy.context.object.scale = (0.2, 0.14, 0.12)
attach(bpy.context.object, "hips", PANTS)
# Nase, damit man die Blickrichtung erkennt
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(0, -0.17, 1.86))
attach(bpy.context.object, "head", SKIN)

for side in ("L", "R"):
    limb(f"upperarm.{side}", 0.06, SHIRT)
    limb(f"forearm.{side}", 0.05, SKIN)
    limb(f"thigh.{side}", 0.08, PANTS)
    limb(f"shin.{side}", 0.065, PANTS)
    x = arm_data.bones[f"foot.{side}"].head_local.x
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -0.06, 0.05))
    bpy.context.object.scale = (0.1, 0.26, 0.08)
    attach(bpy.context.object, f"foot.{side}", SHOES)


# --- Animation --------------------------------------------------------------
# Positionen und Drehungen werden in Welt-Achsen angegeben und in den lokalen
# Raum des jeweiligen Knochens umgerechnet.

def key_bone(name, frame, offset=(0, 0, 0), tilt=0.0):
    """offset: Verschiebung in Welt-Achsen; tilt: Grad um die X-Achse.
    Positive Neigung kippt nach vorn (-Y); bei Armen bedeutet positiv nach hinten."""
    pb = rig.pose.bones[name]
    to_local = arm_data.bones[name].matrix_local.to_3x3().inverted()
    pb.location = to_local @ Vector(offset)
    pb.rotation_quaternion = Quaternion(to_local @ Vector((1, 0, 0)), math.radians(tilt))
    pb.keyframe_insert("location", frame=frame)
    pb.keyframe_insert("rotation_quaternion", frame=frame)


def pose(frame, hips_z=0.0, lean=0.0, arms=0.0, elbows=0.0, feet_z=0.0, feet_y=0.0, head=0.0):
    key_bone("hips", frame, (0, 0, hips_z), lean)
    key_bone("head", frame, tilt=head)
    for side in ("L", "R"):
        key_bone(f"upperarm.{side}", frame, tilt=arms)
        key_bone(f"forearm.{side}", frame, tilt=elbows)
        key_bone(f"foot.{side}", frame, (0, feet_y, feet_z))


pose(1)                                                          # Stehen
pose(6, hips_z=-0.05, arms=-10)                                  # Ausholen
pose(12, hips_z=-0.38, lean=30, arms=55, elbows=-20, head=-20)   # tief in die Hocke, Arme zurück
pose(TAKEOFF, hips_z=0.0, lean=10, arms=-150, elbows=-10)        # Absprung, Arme nach oben
pose(24, hips_z=0.0, lean=5, arms=-120, elbows=-30,
     feet_z=0.45, feet_y=-0.25)                                  # Beine im Flug angezogen
pose(LANDING - 3, hips_z=0.0, lean=10, arms=-60, feet_y=-0.15)   # Beine vor der Landung strecken
pose(LANDING, hips_z=-0.05, lean=15, arms=-50, elbows=-20)       # Aufsetzen
pose(LANDING + 4, hips_z=-0.42, lean=35, arms=-70,
     elbows=-40, head=-25)                                       # Landung abfedern
pose(LANDING + 14, hips_z=-0.08, lean=8, arms=-10, elbows=-10)   # Aufrichten
pose(LANDING + 20)                                               # wieder Stehen
pose(FRAME_END)

# Flugbahn als echte Wurfparabel, Frame für Frame gesetzt (linear).
for frame in range(1, FRAME_END + 1):
    t = min(max((frame - TAKEOFF) / (LANDING - TAKEOFF), 0.0), 1.0)
    rig.location = (0, -JUMP_DISTANCE * t, JUMP_HEIGHT * 4 * t * (1 - t))
    rig.keyframe_insert("location", frame=frame)
for fc in rig.animation_data.action.fcurves:
    if fc.data_path == "location":
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# --- Szene: Boden, Licht, Kamera --------------------------------------------

bpy.ops.mesh.primitive_plane_add(size=40)
bpy.context.object.data.materials.append(material("Boden", (0.75, 0.75, 0.72), 0.9))

bpy.ops.object.light_add(type="SUN", rotation=(math.radians(40), math.radians(-20), math.radians(70)))
bpy.context.object.data.energy = 4
bpy.context.object.data.angle = math.radians(3)

scene.world = bpy.data.worlds.new("Welt")
scene.world.use_nodes = True
background = scene.world.node_tree.nodes["Background"]
background.inputs["Color"].default_value = (0.55, 0.68, 0.9, 1)
background.inputs["Strength"].default_value = 0.35

bpy.ops.object.empty_add(location=(0, -JUMP_DISTANCE / 2, 1.6))
target = bpy.context.object
bpy.ops.object.camera_add(location=(6.5, -3.2, 2.0))
camera = bpy.context.object
camera.data.lens = 48
track = camera.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
scene.camera = camera

# In der Cloud gibt es keine GPU/OpenGL -> Cycles auf der CPU.
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.resolution_x = 480
scene.render.resolution_y = 360
scene.render.filepath = os.path.join(FRAMES_DIR, "f_")

bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
bpy.ops.render.render(animation=True)

subprocess.run(
    ["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
     "-i", os.path.join(FRAMES_DIR, "f_%04d.png"),
     "-vf", "split[a][b];[a]palettegen[p];[b][p]paletteuse", "-loop", "0", GIF_PATH],
    check=True,
)
print("GIF gespeichert:", GIF_PATH)
