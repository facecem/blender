"""Alternativer Charakter im PS2-Look, der sich wie im Charakter-Auswahlmenü dreht.

PS2-Vibe: wenige Polygone mit harten Kanten (Flat Shading), niedrige Auflösung,
die per Nearest-Neighbor hochskaliert wird, und eine reduzierte Farbpalette mit
Bayer-Dithering.

Aufruf:  python3 scripts/ps2_charakter.py
Ergebnis: renders/ps2_charakter.gif und renders/ps2_charakter.blend
"""
import math
import os
import subprocess

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(ROOT, "renders", "frames", "ps2_charakter")
GIF_PATH = os.path.join(ROOT, "renders", "ps2_charakter.gif")
BLEND_PATH = os.path.join(ROOT, "renders", "ps2_charakter.blend")

FRAME_END = 96  # eine volle Drehung, 4 Sekunden bei 24 fps

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAME_END


# --- Materialien ------------------------------------------------------------

def material(name, rgb, roughness=0.7, metallic=0.0, emission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    return m


def plaid(name, color_a, color_b, scale):
    """Karomuster aus zwei überlagerten Streifenmustern, wie ein grobes Low-Res-Textil."""
    m = material(name, color_a)
    nodes, links = m.node_tree.nodes, m.node_tree.links
    coord = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Object"], sep.inputs[0])
    stripes = []
    for axis in ("X", "Z"):
        wave = nodes.new("ShaderNodeMath")
        wave.operation = "PINGPONG"
        scaled = nodes.new("ShaderNodeMath")
        scaled.operation = "MULTIPLY"
        scaled.inputs[1].default_value = scale
        links.new(sep.outputs[axis], scaled.inputs[0])
        links.new(scaled.outputs[0], wave.inputs[0])
        wave.inputs[1].default_value = 1.0
        step = nodes.new("ShaderNodeMath")
        step.operation = "GREATER_THAN"
        step.inputs[1].default_value = 0.72
        links.new(wave.outputs[0], step.inputs[0])
        stripes.append(step)
    both = nodes.new("ShaderNodeMath")
    both.operation = "MAXIMUM"
    links.new(stripes[0].outputs[0], both.inputs[0])
    links.new(stripes[1].outputs[0], both.inputs[1])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*color_a, 1)
    mix.inputs["B"].default_value = (*color_b, 1)
    links.new(both.outputs[0], mix.inputs["Factor"])
    links.new(mix.outputs["Result"], nodes["Principled BSDF"].inputs["Base Color"])
    return m


SKIN = material("Haut", (0.86, 0.72, 0.66), 0.6)
HOODIE = material("Hoodie", (0.05, 0.05, 0.06), 0.9)
PINK = material("Pink", (1.0, 0.08, 0.45), 0.5)
BLACK = material("Schwarz", (0.015, 0.015, 0.02), 0.4)
SILVER = material("Silber", (0.8, 0.8, 0.85), 0.25, metallic=1.0)
SOLE = material("Sohle", (0.55, 0.55, 0.55), 0.8)
CYAN = material("Cyan", (0.0, 0.85, 1.0), 0.4)
PANTS = plaid("Karohose", (0.02, 0.02, 0.025), (0.32, 0.01, 0.05), 11.0)


# --- Low-Poly-Bausteine -----------------------------------------------------

root = bpy.data.objects.new("Charakter", None)
scene.collection.objects.link(root)
upper = bpy.data.objects.new("Oberkoerper", None)  # wippt beim Atmen
scene.collection.objects.link(upper)
upper.parent = root
upper.location.z = 0.95


def part(kind, mat, loc, scale=(1, 1, 1), rot=(0, 0, 0), parent=None, **kwargs):
    """Fügt einen Grundkörper hinzu; Positionen sind Weltkoordinaten in Ruhe."""
    add = {
        "cube": bpy.ops.mesh.primitive_cube_add,
        "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "cyl": bpy.ops.mesh.primitive_cylinder_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
    }[kind]
    if kind == "cube":
        kwargs.setdefault("size", 1)  # scale = Kantenlängen
    if kind == "sphere":
        kwargs.setdefault("segments", 8)
        kwargs.setdefault("ring_count", 6)
    if kind in ("cone", "cyl"):
        kwargs.setdefault("vertices", 6)
    if kind == "torus":
        kwargs.setdefault("major_segments", 10)
        kwargs.setdefault("minor_segments", 4)
    add(location=loc, rotation=[math.radians(r) for r in rot], **kwargs)
    obj = bpy.context.object
    obj.scale = scale
    obj.data.materials.append(mat)
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent or upper
    obj.matrix_world = world
    return obj


bpy.context.view_layer.update()

# Beine: weite Karohose, Plateau-Boots
for x in (-0.13, 0.13):
    part("cone", PANTS, (x, 0, 0.56), radius1=0.17, radius2=0.13, depth=0.78, parent=root)
    part("cube", BLACK, (x, -0.05, 0.19), (0.17, 0.3, 0.16), parent=root)
    part("cube", SOLE, (x, -0.05, 0.055), (0.18, 0.32, 0.11), parent=root)
    for z in (0.2, 0.25):  # Schnallen
        part("cube", SILVER, (x, -0.2, z), (0.14, 0.01, 0.018), parent=root)

# Nietengürtel und Wallet-Chain
part("cyl", BLACK, (0, 0, 0.97), radius=0.25, depth=0.07, vertices=8)
for i in range(8):
    a = math.tau * i / 8
    part("cube", SILVER, (0.255 * math.sin(a), -0.255 * math.cos(a), 0.97),
         (0.03, 0.03, 0.03), (0, 0, math.degrees(a)))
for i in range(7):
    t = i / 6
    part("torus", SILVER, (0.22 + 0.05 * t, -0.15 + 0.25 * t, 0.94 - 0.18 * math.sin(math.pi * t)),
         rot=(90 * (i % 2), 0, 60), major_radius=0.022, minor_radius=0.007)

# Oversized Hoodie mit Kapuze, Bauchtasche und pinken Kordeln
part("cone", HOODIE, (0, 0, 1.3), (1, 0.72, 1), radius1=0.31, radius2=0.25, depth=0.62, vertices=8)
part("cube", HOODIE, (0, -0.215, 1.12), (0.3, 0.03, 0.14))
part("cube", PINK, (0, -0.205, 1.32), (0.4, 0.01, 0.03))
part("sphere", HOODIE, (0, 0.13, 1.6), (0.24, 0.15, 0.12))
for x in (-0.06, 0.06):
    part("cyl", PINK, (x, -0.19, 1.48), radius=0.012, depth=0.2, vertices=4)
for x in (-0.3, 0.3):
    part("sphere", HOODIE, (x, 0, 1.53), (0.12, 0.12, 0.11))
    side = 1 if x > 0 else -1
    part("cone", HOODIE, (x + 0.06 * side, 0, 1.25), rot=(0, 10 * side, 0),
         radius1=0.1, radius2=0.08, depth=0.5)
    part("cube", SKIN, (x + 0.1 * side, -0.01, 0.95), (0.08, 0.1, 0.12))
    part("cube", BLACK, (x + 0.1 * side, -0.01, 0.99), (0.085, 0.105, 0.05))  # fingerlose Handschuhe

# Hals, Choker, Kopfhörer um den Hals
part("cyl", SKIN, (0, 0, 1.64), radius=0.07, depth=0.12)
part("torus", BLACK, (0, 0, 1.66), major_radius=0.075, minor_radius=0.014, major_segments=8)
part("torus", SILVER, (0, -0.088, 1.64), rot=(90, 0, 0), major_radius=0.016, minor_radius=0.005)
for x in (-0.15, 0.15):
    part("cyl", CYAN, (x, -0.03, 1.6), rot=(0, 90, 0), radius=0.06, depth=0.04, vertices=8)
part("torus", BLACK, (0, 0.03, 1.6), (1, 0.7, 1), major_radius=0.15, minor_radius=0.015)

# Kopf: grob, leicht übergroß, wie ein PS2-Charaktermodell
head = part("sphere", SKIN, (0, 0, 1.86), (0.2, 0.19, 0.22))
for x in (-0.075, 0.075):
    part("cube", BLACK, (x, -0.178, 1.88), (0.055, 0.01, 0.022))           # Augen
    part("cube", BLACK, (x * 1.35, -0.168, 1.895), (0.03, 0.01, 0.008),
         (0, -20 if x > 0 else 20, 0))                                    # Eyeliner-Flügel
part("cube", (material("Lippen", (0.25, 0.02, 0.08), 0.3)), (0, -0.185, 1.77), (0.06, 0.01, 0.012))
part("sphere", SILVER, (0.03, -0.19, 1.755), (0.012, 0.012, 0.012), segments=6, ring_count=4)  # Lippenpiercing
part("sphere", SILVER, (0.09, -0.17, 1.935), (0.01, 0.01, 0.01), segments=6, ring_count=4)     # Augenbraue
for z in (1.84, 1.88):
    part("sphere", SILVER, (0.2, 0.0, z), (0.012, 0.012, 0.012), segments=6, ring_count=4)    # Ohr

# Frisur: schwarze Haare mit pinken Strähnen, Pony über einem Auge, Spikes hinten
part("sphere", BLACK, (0, 0.03, 1.92), (0.225, 0.22, 0.2))
for x, z, tilt, mat in [(-0.13, 1.88, 25, BLACK), (-0.07, 1.86, 15, PINK), (-0.01, 1.87, 5, BLACK),
                        (0.06, 1.95, -15, BLACK)]:
    part("cone", mat, (x, -0.17, z), rot=(-160, tilt, 0), radius1=0.07, radius2=0, depth=0.24, vertices=4)
for i, (x, z, mat) in enumerate([(-0.14, 2.0, BLACK), (-0.05, 2.06, PINK), (0.05, 2.06, BLACK),
                                 (0.14, 2.0, PINK), (0.0, 1.95, BLACK)]):
    part("cone", mat, (x, 0.12, z), rot=(-40 + 15 * (i % 2), 0, -x * 200),
         radius1=0.06, radius2=0, depth=0.3, vertices=4)


# --- Animation: Drehteller und Atmen ----------------------------------------

for frame in range(1, FRAME_END + 2):
    t = (frame - 1) / FRAME_END
    root.rotation_euler.z = math.tau * t
    root.keyframe_insert("rotation_euler", frame=frame, index=2)
    upper.location.z = 0.95 + 0.012 * math.sin(math.tau * 2 * t)
    upper.keyframe_insert("location", frame=frame, index=2)
    head.rotation_euler.x = math.radians(3 * math.sin(math.tau * 2 * t + 0.6))
    head.keyframe_insert("rotation_euler", frame=frame, index=0)
for obj in (root, upper, head):
    for fc in obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# --- Bühne: Podest mit Leuchtring, Karoboden, farbige Rim-Lights ------------

bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.6, depth=0.1, location=(0, 0, -0.05))
bpy.context.object.data.materials.append(material("Podest", (0.06, 0.04, 0.1), 0.5))
bpy.ops.mesh.primitive_torus_add(major_radius=0.62, minor_radius=0.025, major_segments=24,
                                 minor_segments=4, location=(0, 0, 0.0))
bpy.context.object.data.materials.append(material("Leuchtring", (0.0, 0.9, 1.0), emission=6))
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.1))
bpy.context.object.data.materials.append(plaid("Boden", (0.03, 0.01, 0.06), (0.12, 0.03, 0.2), 0.8))

scene.world = bpy.data.worlds.new("Welt")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.01, 0.09, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6


def light(kind, loc, rgb, energy, size=1.0):
    data = bpy.data.lights.new(kind, kind)
    data.color, data.energy = rgb, energy
    if kind == "AREA":
        data.size = size
    obj = bpy.data.objects.new(kind, data)
    obj.location = loc
    obj.constraints.new("TRACK_TO").target = target
    scene.collection.objects.link(obj)


target = bpy.data.objects.new("Ziel", None)
target.location = (0, 0, 1.1)
scene.collection.objects.link(target)
light("AREA", (-2.5, -3.5, 3.0), (1.0, 0.95, 0.9), 450, 2.0)   # Key-Light
light("AREA", (-2.5, 2.5, 2.0), (1.0, 0.1, 0.6), 400, 1.0)     # Rim magenta
light("AREA", (2.5, 2.5, 2.0), (0.0, 0.8, 1.0), 400, 1.0)      # Rim cyan

cam_data = bpy.data.cameras.new("Kamera")
cam_data.lens = 58
camera = bpy.data.objects.new("Kamera", cam_data)
camera.location = (0, -5.4, 1.4)
camera.constraints.new("TRACK_TO").target = target
scene.collection.objects.link(camera)
scene.camera = camera

# Bewusst niedrige Auflösung; hochskaliert wird pixelig per Nearest-Neighbor.
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x = 320
scene.render.resolution_y = 240
scene.render.filepath = os.path.join(FRAMES_DIR, "f_")

bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
bpy.ops.render.render(animation=True)

subprocess.run(
    ["ffmpeg", "-loglevel", "error", "-y", "-framerate", "24",
     "-i", os.path.join(FRAMES_DIR, "f_%04d.png"),
     "-vf", "scale=640:480:flags=neighbor,split[a][b];"
            "[a]palettegen=max_colors=48[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
     "-loop", "0", GIF_PATH],
    check=True,
)
print("GIF gespeichert:", GIF_PATH)
