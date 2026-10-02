"""Rotierender Würfel: rendert 24 Frames und baut daraus ein GIF.

Aufruf:  python3 scripts/wuerfel_rotation.py
(lokal alternativ: blender --background --python scripts/wuerfel_rotation.py)
"""
import math
import os
import subprocess

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(ROOT, "renders", "frames", "wuerfel_rotation")
GIF_PATH = os.path.join(ROOT, "renders", "wuerfel_rotation.gif")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
cube = bpy.context.object
material = bpy.data.materials.new("Wuerfel")
material.use_nodes = True
material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.25, 0.1, 1)
cube.data.materials.append(material)
for frame, angle in [(1, 0), (24, math.pi)]:
    cube.rotation_euler.z = angle
    cube.keyframe_insert("rotation_euler", frame=frame)

bpy.ops.object.camera_add(location=(6, -6, 5))
camera = bpy.context.object
camera.rotation_euler = (math.radians(63), 0, math.radians(45))
scene.camera = camera
bpy.ops.mesh.primitive_plane_add(size=20)  # Boden

# Sonne schräg von der Seite, damit die Würfelseiten Licht abbekommen.
bpy.ops.object.light_add(type="SUN", rotation=(math.radians(55), 0, math.radians(110)))
bpy.context.object.data.energy = 5

# Helle Umgebung statt schwarzem Hintergrund.
scene.world = bpy.data.worlds.new("Welt")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.7, 0.85, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
scene.view_settings.look = "AgX - Medium High Contrast"

# In der Cloud gibt es keine GPU/OpenGL -> Cycles auf der CPU.
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.resolution_x = 320
scene.render.resolution_y = 240
scene.frame_end = 24
scene.render.filepath = os.path.join(FRAMES_DIR, "f_")

bpy.ops.render.render(animation=True)

subprocess.run(
    ["ffmpeg", "-loglevel", "error", "-y", "-framerate", "24",
     "-i", os.path.join(FRAMES_DIR, "f_%04d.png"), "-vf", "fps=12", GIF_PATH],
    check=True,
)
print("GIF gespeichert:", GIF_PATH)
