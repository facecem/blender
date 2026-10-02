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

bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.object
for frame, angle in [(1, 0), (24, math.pi)]:
    cube.rotation_euler.z = angle
    cube.keyframe_insert("rotation_euler", frame=frame)

bpy.ops.object.camera_add(location=(6, -6, 4))
camera = bpy.context.object
camera.rotation_euler = (math.radians(63), 0, math.radians(45))
scene.camera = camera
bpy.ops.object.light_add(type="SUN")

# In der Cloud gibt es keine GPU/OpenGL -> Cycles auf der CPU.
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8
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
