"""Realistischer Charakter im Stil später PS2-Spiele (San Andreas, Def Jam & Co.).

Basis ist das freie MakeHuman-Modell (CC0) aus dem MPFB2-Repository: Körper,
Skelett und Gewichtung werden beim ersten Lauf nach assets/makehuman geladen.
Daraus entsteht ein eigener Alt-Charakter: sehr helle Haut, lockere dunkle
Haare, Flanellhemd über Band-Shirt, Septum, Ohrringe und Kette. Haut, Augenbrauen
und Lippen sind wie damals als Vertex-Farben
gemalt; das Bild wird klein gerendert und weich hochskaliert.

Aufruf:  python3 scripts/ps2_realistisch.py
Ergebnis: renders/ps2_realistisch.gif und renders/ps2_realistisch.blend
"""
import gzip
import json
import math
import os
import subprocess
import urllib.request

import bpy
import numpy as np
from mathutils import Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets", "makehuman")
FRAMES_DIR = os.path.join(ROOT, "renders", "frames", "ps2_realistisch")
GIF_PATH = os.path.join(ROOT, "renders", "ps2_realistisch.gif")
BLEND_PATH = os.path.join(ROOT, "renders", "ps2_realistisch.blend")
MPFB = "https://raw.githubusercontent.com/makehumancommunity/mpfb2/master/src/mpfb/data/"

FRAME_END = 72
RENDER_SIZE = (320, 400)  # klein rendern, danach weich auf das Doppelte skalieren


def asset(rel):
    path = os.path.join(ASSETS, rel.replace("/", "_"))
    if not os.path.exists(path):
        os.makedirs(ASSETS, exist_ok=True)
        print("Lade", rel)
        urllib.request.urlretrieve(MPFB + rel, path)
    return path


# --- MakeHuman-Basismodell laden und formen ----------------------------------

def load_obj(path):
    verts, uvs, faces = [], [], {}
    group = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                group = line.split()[1]
            elif line.startswith("f "):
                ids = [t.split("/") for t in line.split()[1:]]
                faces.setdefault(group, []).append(
                    ([int(i[0]) - 1 for i in ids], [int(i[1]) - 1 for i in ids]))
    return np.array(verts), np.array(uvs), faces


def apply_target(verts, rel, weight):
    with gzip.open(asset(rel), "rt") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 4 and not line.startswith("#"):
                verts[int(parts[0])] += weight * np.array([float(p) for p in parts[1:]])


obj_verts, obj_uvs, obj_faces = load_obj(asset("3dobjs/base.obj"))
# Eigener, gemischter Typ: Mittel aus den drei Ethnie-Zielen, etwas muskulöser.
for ethnic in ("african", "asian", "caucasian"):
    apply_target(obj_verts, f"targets/macrodetails/{ethnic}-male-young.target.gz", 1 / 3)
apply_target(obj_verts, "targets/macrodetails/universal-male-young-maxmuscle-averageweight.target.gz", 0.35)

# MakeHuman: Dezimeter, Y nach oben -> Blender: Meter, Z nach oben, Blick nach -Y
VERTS = np.column_stack([obj_verts[:, 0], -obj_verts[:, 2], obj_verts[:, 1]]) * 0.1
VERTS[:, 2] -= VERTS[:, 2].min()  # Füße auf den Boden

WEIGHTS = json.load(open(asset("rigs/standard/weights.default.json")))["weights"]
RIG = json.load(open(asset("rigs/standard/rig.default.json")))

# Dominanter Knochen je Vertex: daraus werden Kleidungsbereiche abgeleitet.
best = np.zeros(len(VERTS))
DOMINANT = np.empty(len(VERTS), dtype=object)
for bone_name, pairs in WEIGHTS.items():
    for i, w in pairs:
        if w > best[i]:
            best[i], DOMINANT[i] = w, bone_name


def group_center(name):
    ids = {i for f, _ in obj_faces[name] for i in f}
    return Vector(VERTS[sorted(ids)].mean(axis=0))


ORIG_INDEX = {}  # Mesh-Name -> ursprüngliche Vertex-Nummern im OBJ


def build_mesh(name, groups, keep=None):
    """Mesh aus OBJ-Gruppen, mit UVs und Skelett-Gewichten; keep(face_ids) filtert Flächen."""
    faces, uv_faces = [], []
    for g in groups:
        for f, uv in obj_faces[g]:
            if keep is None or keep(f):
                faces.append(f)
                uv_faces.append(uv)
    used = sorted({i for f in faces for i in f})
    remap = {old: new for new, old in enumerate(used)}
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(VERTS[used].tolist(), [], [[remap[i] for i in f] for f in faces])
    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_layer.data.foreach_set("uv", np.array([obj_uvs[i] for uv in uv_faces for i in uv]).ravel().astype(np.float32))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for bone_name, pairs in WEIGHTS.items():
        pairs = [(remap[i], w) for i, w in pairs if i in remap]
        if pairs:
            vg = obj.vertex_groups.new(name=bone_name)
            for i, w in pairs:
                vg.add([i], w, "REPLACE")
    for poly in mesh.polygons:
        poly.use_smooth = True
    ORIG_INDEX[name] = used
    return obj


# --- Skelett ----------------------------------------------------------------

def joint(spec):
    if spec["strategy"] == "CUBE":
        return group_center(spec["cube_name"])
    if spec["strategy"] == "VERTEX":
        return Vector(VERTS[spec["vertex_index"]])
    return Vector(VERTS[spec["vertex_indices"]].mean(axis=0))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

arm_data = bpy.data.armatures.new("Skelett")
rig = bpy.data.objects.new("Charakter", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for name, spec in RIG.items():
    b = arm_data.edit_bones.new(name)
    b.head, b.tail = joint(spec["head"]), joint(spec["tail"])
    b.roll = spec["roll"]
for name, spec in RIG.items():
    if spec.get("parent"):
        b = arm_data.edit_bones[name]
        b.parent = arm_data.edit_bones[spec["parent"]]
        b.use_connect = spec.get("use_connect", False)
bpy.ops.object.mode_set(mode="OBJECT")
for pb in rig.pose.bones:
    pb.rotation_mode = "QUATERNION"


def skin_to_rig(obj):
    obj.parent = rig
    obj.modifiers.new("Skelett", "ARMATURE").object = rig


# --- Körperteile --------------------------------------------------------------

TOP = ("spine", "clavicle", "shoulder", "upperarm", "lowerarm", "breast")
LEGS = ("upperleg", "lowerleg", "pelvis", "root")
FEET = ("foot", "toe")


def region(prefixes):
    def keep(face):
        return all(str(DOMINANT[i]).startswith(prefixes) for i in face)
    return keep


body = build_mesh("Koerper", ["body"])
eyes = build_mesh("Augen", ["helper-l-eye", "helper-r-eye"])
EYE_Z = group_center("joint-l-eye").z


EYE_Y = group_center("joint-l-eye").y


def scalp(face):
    """Behaarte Kopfhaut: über der Stirn, an den Seiten über den Ohren, hinten bis zum Nacken."""
    p = VERTS[face]
    if not all(str(DOMINANT[i]).startswith("head") for i in face):
        return False
    y, z = p[:, 1].mean(), p[:, 2].min()
    if y < EYE_Y + 0.04:
        return z > EYE_Z + 0.05
    if y < EYE_Y + 0.11:
        return z > EYE_Z + 0.012
    return z > EYE_Z - 0.05


hair = build_mesh("Haare", ["body"], scalp)
NECK_Z = group_center("joint-neck").z - 0.035


def sweater_part(face):
    """Oberkörper und Arme bis zum Handgelenk, mit gerader Rundhals-Kante."""
    return region(TOP)(face) and VERTS[face][:, 2].max() < NECK_Z


sweater = build_mesh("Hemd", ["helper-tights"], sweater_part)
pants = build_mesh("Hose", ["helper-tights"], region(LEGS))
shoes = build_mesh("Schuhe", ["helper-tights"], region(FEET))
for obj in (body, eyes, hair, sweater, pants, shoes):
    skin_to_rig(obj)


def push_out(obj, amount, levels=1):
    """Kleidung leicht aufblähen und etwas glätten (vor dem Skelett-Modifier)."""
    sub = obj.modifiers.new("Glatt", "SUBSURF")
    sub.levels = sub.render_levels = levels
    disp = obj.modifiers.new("Abstand", "DISPLACE")
    disp.strength, disp.mid_level = amount, 0.0
    sol = obj.modifiers.new("Dicke", "SOLIDIFY")
    sol.thickness, sol.offset = 0.006, 1.0
    # Reihenfolge: Glatt, Abstand, Dicke vor dem Skelett
    for i, mod_name in enumerate(("Glatt", "Abstand", "Dicke")):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_move_to_index(modifier=mod_name, index=i)


push_out(sweater, 0.012)
push_out(pants, 0.006)
push_out(shoes, 0.018)
push_out(hair, 0.016)
# Strähnige, unruhige Oberfläche für das Deckhaar
tufts = bpy.data.textures.new("Straehnen", "CLOUDS")
tufts.noise_scale = 0.03
messy = hair.modifiers.new("Straehnen", "DISPLACE")
messy.texture, messy.strength, messy.texture_coords = tufts, 0.012, "LOCAL"
messy.mid_level = 0.3
bpy.context.view_layer.objects.active = hair
bpy.ops.object.modifier_move_to_index(modifier="Straehnen", index=2)
eye_sub = eyes.modifiers.new("Glatt", "SUBSURF")
bpy.context.view_layer.objects.active = eyes
bpy.ops.object.modifier_move_to_index(modifier="Glatt", index=0)


# --- Vertex-Farben: Haut, Brauen, Lippen, Bart --------------------------------

EYE_L, EYE_R = group_center("joint-l-eye"), group_center("joint-r-eye")
MOUTH = group_center("joint-mouth")
HEAD_TOP = Vector(VERTS[[i for f, _ in obj_faces["body"] for i in f]].max(axis=0))
co = VERTS[ORIG_INDEX["Koerper"]]


def soft(x, edge, width):
    return np.clip((x - edge) / width + 0.5, 0, 1)


skin = np.tile([0.93, 0.87, 0.84], (len(co), 1))  # sehr helle, fast weiße Haut
front = co[:, 1] < EYE_L.y + 0.02
face_x = np.abs(co[:, 0])
# Augenbrauen: Bogen über jedem Auge
brow_z = EYE_L.z + 0.021 + 0.004 * np.cos((face_x - abs(EYE_L.x)) * 40)
brow = (front & (face_x > 0.008) & (face_x < abs(EYE_L.x) + 0.03)
        & (np.abs(co[:, 2] - brow_z) < 0.0055 - 0.06 * np.maximum(face_x - abs(EYE_L.x), 0)))
# Lippen
lips = front & (np.abs(co[:, 2] - (MOUTH.z - 0.034)) < 0.006) & (face_x < 0.024) & (co[:, 1] < MOUTH.y - 0.085)
# leichte Augenringe
socket = front & ((np.hypot(co[:, 0] - EYE_L.x, co[:, 2] - EYE_L.z) < 0.02)
                  | (np.hypot(co[:, 0] - EYE_R.x, co[:, 2] - EYE_R.z) < 0.02))
color = skin.copy()
color[socket] *= [0.86, 0.84, 0.88]
color[lips] = [0.84, 0.64, 0.64]
color[brow] = [0.12, 0.09, 0.08]
color *= 0.96 + 0.04 * np.random.default_rng(1).random((len(co), 1))  # leicht fleckige Haut


def paint(obj, colors):
    attr = obj.data.color_attributes.new("Farbe", "FLOAT_COLOR", "POINT")
    attr.data.foreach_set("color", np.column_stack([colors, np.ones(len(colors))]).ravel().astype(np.float32))


paint(body, color ** 2.2)  # sRGB -> linear

# Haare: natürliches Schwarzbraun mit leichten Farbschwankungen
HAIR_RGB = np.array([0.07, 0.05, 0.045])
hco = VERTS[ORIG_INDEX["Haare"]]
paint(hair, (HAIR_RGB * (0.8 + 0.4 * np.random.default_rng(2).random((len(hco), 1)))) ** 2.2)


# --- Materialien ---------------------------------------------------------------

def mat(name, rgb=None, roughness=0.6, use_vcol=False, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if use_vcol:
        vc = nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Farbe"
        m.node_tree.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    return m


def flannel_texture(name, size=32):
    """Rot-schwarzes Flanell-Karo als 32x32-Textur wie aus PS2-Zeiten."""
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:size, 0:size]
    band_x, band_y = (x // 8) % 2 == 0, (y // 8) % 2 == 0
    red, black = np.array([0.5, 0.05, 0.05]), np.array([0.04, 0.03, 0.03])
    weave = (band_x.astype(float) + band_y.astype(float)) / 2  # 0, 0.5 oder 1
    rgb = black + weave[..., None] * (red - black)
    thin = (x % 8 == 4) | (y % 8 == 4)  # feine helle Linien im Karo
    rgb[thin] = rgb[thin] * 0.5 + 0.18
    rgb *= 0.9 + 0.2 * rng.random((size, size, 1))
    img = bpy.data.images.new(name, size, size)
    img.pixels.foreach_set(np.concatenate([rgb ** 2.2, np.ones((size, size, 1))], axis=-1).ravel().astype(np.float32))
    img.pack()
    return img


SKIN = mat("Haut", roughness=0.7, use_vcol=True)
HAIR = mat("Haare", roughness=0.5, use_vcol=True)
JEANS = mat("Jeans", (0.03, 0.04, 0.06), 0.85)
SHOE = mat("Schuhe", (0.02, 0.02, 0.02), 0.4)
SILVER = mat("Silber", (0.85, 0.85, 0.9), 0.2, metallic=1.0)
EYE = mat("Auge", roughness=0.15, use_vcol=True)
SWEATER = mat("Flanellhemd", (0.1, 0.1, 0.1), roughness=0.9)
tex = SWEATER.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = flannel_texture("Flanell")
mapping = SWEATER.node_tree.nodes.new("ShaderNodeMapping")
mapping.inputs["Scale"].default_value = (3, 3, 3)
tex.projection, tex.projection_blend = "BOX", 0.3
tex.interpolation = "Closest"
obj_coord = SWEATER.node_tree.nodes.new("ShaderNodeTexCoord")
SWEATER.node_tree.links.new(obj_coord.outputs["Object"], mapping.inputs["Vector"])
SWEATER.node_tree.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
SWEATER.node_tree.links.new(tex.outputs["Color"], SWEATER.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

for obj, m in ((body, SKIN), (hair, HAIR), (sweater, SWEATER), (pants, JEANS), (shoes, SHOE), (eyes, EYE)):
    obj.data.materials.append(m)

# Augen: Iris/Pupille per Vertex-Farbe nach Abstand zur Blickachse
eco = VERTS[ORIG_INDEX["Augen"]]
ecol = np.ones((len(eco), 3)) * 0.85
for c in (EYE_L, EYE_R):
    near = np.linalg.norm(eco - np.array(c), axis=1) < 0.02
    radial = np.hypot(eco[:, 0] - c.x, eco[:, 2] - c.z)
    ecol[near & (radial < 0.0065)] = [0.18, 0.1, 0.05]
    ecol[near & (radial < 0.003)] = [0.01, 0.01, 0.01]
paint(eyes, ecol ** 2.2)


# --- Schmuck: Kette, Septum, Ohrringe ---------------------------------

def bone_child(obj, bone_name):
    bpy.context.view_layer.update()  # Skalierung erst übernehmen, dann Weltmatrix sichern
    world = obj.matrix_world.copy()
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    bpy.context.view_layer.update()
    obj.matrix_world = world


def ring(loc, radius, thickness, rot, bone_name):
    bpy.ops.mesh.primitive_torus_add(location=loc, rotation=rot, major_radius=radius,
                                     minor_radius=thickness, major_segments=12, minor_segments=4)
    o = bpy.context.object
    o.data.materials.append(SILVER)
    bpy.ops.object.shade_smooth()
    bone_child(o, bone_name)
    return o


def front_point(z, x=0.0, tol=0.004):
    """Vorderster Hautpunkt auf Höhe z (für Nase, Lippe)."""
    sel = (np.abs(co[:, 2] - z) < tol) & (np.abs(co[:, 0] - x) < tol)
    return Vector(co[sel][np.argmin(co[sel][:, 1])])


cand = co[(co[:, 2] > EYE_L.z - 0.06) & (co[:, 2] < EYE_L.z - 0.01) & (np.abs(co[:, 0]) < 0.006)]
nose_tip = Vector(cand[np.argmin(cand[:, 1])])
ring(nose_tip + Vector((0, 0.012, -0.011)), 0.0045, 0.001, (math.radians(80), 0, 0), "head")  # Septum
for side in (1, -1):
    ear = co[(np.sign(co[:, 0]) == side) & (np.abs(co[:, 2] - (EYE_L.z - 0.035)) < 0.006)]
    lobe = Vector(ear[np.argmax(np.abs(ear[:, 0]))])
    ring(lobe + Vector((0, 0, -0.006)), 0.007, 0.0014, (0, math.radians(90), 0), "head")
neck = group_center("joint-neck")

# Kragen des schwarzen Band-Shirts unter dem Flanellhemd verdeckt die Halskante
bpy.ops.mesh.primitive_torus_add(location=(0, neck.y + 0.008, NECK_Z - 0.002), major_radius=0.07,
                                 minor_radius=0.016, major_segments=16, minor_segments=6)
collar = bpy.context.object
collar.scale = (1.15, 1.0, 0.8)
collar.data.materials.append(mat("Shirt", (0.02, 0.02, 0.02), 0.9))
bpy.ops.object.shade_smooth()
bone_child(collar, "spine05")

# Lockere, etwas strubbelige Frisur: flache Strähnen, die am Kopf nach unten fallen,
# vorne als Pony in die Stirn. Strähnen-Kegel wie bei PS2-Haarmodellen.
STRAND = mat("Straehne", roughness=0.5, use_vcol=True)
rng = np.random.default_rng(3)
hair_mesh = hair.data
for idx in rng.choice(len(hair_mesh.vertices), size=min(110, len(hair_mesh.vertices)), replace=False):
    v = hair_mesh.vertices[idx]
    n = v.normal.normalized()
    fall = Vector((0, -0.6 if v.co.y < EYE_Y + 0.04 else 0.3, -1))  # vorne in die Stirn, sonst nach unten/hinten
    direction = (fall - n * fall.dot(n)).normalized() + n * 0.25
    direction.normalize()
    length = rng.uniform(0.035, 0.06)
    base = v.co + n * 0.016
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=rng.uniform(0.012, 0.018), radius2=0.002,
                                    depth=length, location=base + direction * length / 2,
                                    rotation=direction.to_track_quat("Z", "Y").to_euler())
    strand = bpy.context.object
    strand.scale.y = 0.45  # flach wie eine Haarsträhne
    strand.data.materials.append(STRAND)
    paint(strand, np.tile(HAIR_RGB * rng.uniform(0.8, 1.3), (len(strand.data.vertices), 1)) ** 2.2)
    bpy.ops.object.shade_smooth()
    bone_child(strand, "head")
for i in range(26):  # Kette um den Hals
    a = math.tau * i / 26
    p = Vector((0.062 * math.sin(a), neck.y - 0.005 + 0.055 * -math.cos(a),
                neck.z - 0.045 - 0.035 * max(0, -math.cos(a)) ** 2))
    ring(p, 0.006, 0.0016, (math.radians(90) * (i % 2), 0, a), "neck01")


# --- Pose und Animation ------------------------------------------------------------

def rot_world(name, frame, *turns):
    """Dreht einen Knochen um Welt-Achsen (bezogen auf seine Ruhelage); turns = (Achse, Grad)."""
    q = Quaternion()
    for axis, deg in turns:
        q = Quaternion(axis, math.radians(deg)) @ q
    axis, angle = q.to_axis_angle()
    to_local = arm_data.bones[name].matrix_local.to_3x3().inverted()
    pb = rig.pose.bones[name]
    pb.rotation_quaternion = Quaternion((to_local @ axis).normalized(), angle)
    pb.keyframe_insert("rotation_quaternion", frame=frame)


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)

# Rechte Hand per IK: Zielpunkt vor der Brust, Ellbogen zeigt nach außen unten
HAND_POS = Vector((-0.05, -0.33, 1.44))
hand_target = bpy.data.objects.new("HandZiel", None)
elbow_pole = bpy.data.objects.new("EllbogenZiel", None)
elbow_pole.location = (-0.6, -0.1, 1.0)
for o in (hand_target, elbow_pole):
    scene.collection.objects.link(o)
hand_ik = rig.pose.bones["lowerarm02.R"].constraints.new("IK")
hand_ik.target, hand_ik.pole_target, hand_ik.chain_count = hand_target, elbow_pole, 4
hand_ik.pole_angle = math.radians(-90)


def pose(frame, head_turn=0.0, head_nod=0.0, breathe=0.0, gesture=0.0):
    """gesture 0..1: rechte Hand hoch, Finger gespreizt Richtung Kamera."""
    g = gesture
    rot_world("upperarm01.L", frame, (Y, 22 - 2 * breathe))
    rot_world("lowerarm01.L", frame, (X, -8))
    rot_world("upperarm01.R", frame, (Y, -22 + 2 * breathe))
    rot_world("lowerarm01.R", frame, (X, -8))
    rot_world("wrist.R", frame, (X, -40 * g), (Z, 60 * g), (Y, 70 * g))
    hand_ik.influence = g
    hand_ik.keyframe_insert("influence", frame=frame)
    hand_target.location = HAND_POS + Vector((0.01 * math.sin(frame * 0.9), 0, 0.008 * math.sin(frame * 0.5)))
    hand_target.keyframe_insert("location", frame=frame)
    for i, spread in zip(range(2, 6), (-12, -4, 4, 12)):
        rot_world(f"finger{i}-1.R", frame, (Y, spread * g))
    rot_world("spine03", frame, (X, -1.5 * breathe), (Z, 8 * g))
    rot_world("neck01", frame, (X, head_nod * 0.4))
    rot_world("head", frame, (X, head_nod), (Z, head_turn), (Y, -6 * g))


for f in range(1, FRAME_END + 2, 3):
    t = (f - 1) / FRAME_END
    # Hand hoch zwischen 30 % und 75 % der Schleife, weich ein- und ausgeblendet
    g = min(1.0, max(0.0, min((t - 0.25) / 0.1, (0.8 - t) / 0.1)))
    g = g * g * (3 - 2 * g)
    pose(f,
         head_turn=8 * math.sin(math.tau * t),
         head_nod=6 * max(0, math.sin(math.tau * 2 * t)) ** 3 - 2,  # zweimal lässig nicken
         breathe=math.sin(math.tau * 2 * t),
         gesture=g)


# --- Bühne: verputzte Wand mit orangem Feld, weiches Licht --------------------------

def wall_material():
    m = mat("Wand", (0.8, 0.75, 0.62), 0.95)
    n, l = m.node_tree.nodes, m.node_tree.links
    coord = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(coord.outputs["Object"], sep.inputs[0])

    def band(axis, lo, hi):
        a = n.new("ShaderNodeMath"); a.operation = "GREATER_THAN"; a.inputs[1].default_value = lo
        b = n.new("ShaderNodeMath"); b.operation = "LESS_THAN"; b.inputs[1].default_value = hi
        l.new(sep.outputs[axis], a.inputs[0]); l.new(sep.outputs[axis], b.inputs[0])
        m_ = n.new("ShaderNodeMath"); m_.operation = "MULTIPLY"
        l.new(a.outputs[0], m_.inputs[0]); l.new(b.outputs[0], m_.inputs[1])
        return m_

    bx, by = band("X", -0.4, 0.25), band("Y", 0.04, 0.2)
    panel = n.new("ShaderNodeMath"); panel.operation = "MULTIPLY"
    l.new(bx.outputs[0], panel.inputs[0]); l.new(by.outputs[0], panel.inputs[1])
    noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 25
    l.new(coord.outputs["Object"], noise.inputs["Vector"])
    plaster = n.new("ShaderNodeMix"); plaster.data_type = "RGBA"
    plaster.inputs["A"].default_value = (0.55, 0.5, 0.4, 1)
    plaster.inputs["B"].default_value = (0.68, 0.63, 0.5, 1)
    l.new(noise.outputs["Fac"], plaster.inputs["Factor"])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    l.new(panel.outputs[0], mix.inputs["Factor"])
    l.new(plaster.outputs["Result"], mix.inputs["A"])
    mix.inputs["B"].default_value = (0.75, 0.2, 0.06, 1)
    l.new(mix.outputs["Result"], n["Principled BSDF"].inputs["Base Color"])
    return m


bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.9, 1.5), rotation=(math.radians(90), 0, 0))
wall = bpy.context.object
wall.scale = (4, 3, 1)
wall.data.materials.append(wall_material())

scene.world = bpy.data.worlds.new("Welt")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.72, 0.65, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5

target = bpy.data.objects.new("Ziel", None)
target.location = (0, 0, 1.5)
scene.collection.objects.link(target)


def light(loc, rgb, energy, size):
    data = bpy.data.lights.new("Licht", "AREA")
    data.color, data.energy, data.size = rgb, energy, size
    obj = bpy.data.objects.new("Licht", data)
    obj.location = loc
    obj.constraints.new("TRACK_TO").target = target
    scene.collection.objects.link(obj)


light((-1.4, -1.8, 2.4), (1.0, 0.93, 0.85), 95, 1.2)
light((1.5, -1.0, 1.8), (0.85, 0.9, 1.0), 25, 2.0)

cam_data = bpy.data.cameras.new("Kamera")
cam_data.lens = 45
camera = bpy.data.objects.new("Kamera", cam_data)
camera.location = (0.15, -0.85, 1.5)
cam_target = bpy.data.objects.new("Kameraziel", None)
cam_target.location = (0.0, 0.0, 1.56)
scene.collection.objects.link(cam_target)
camera.constraints.new("TRACK_TO").target = cam_target
scene.collection.objects.link(camera)
scene.camera = camera

scene.frame_start, scene.frame_end = 1, FRAME_END
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x, scene.render.resolution_y = RENDER_SIZE
scene.render.filepath = os.path.join(FRAMES_DIR, "f_")

if __name__ == "__main__":
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    bpy.ops.render.render(animation=True)
    w, h = RENDER_SIZE
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-framerate", "24",
         "-i", os.path.join(FRAMES_DIR, "f_%04d.png"),
         "-vf", f"scale={w * 2}:{h * 2}:flags=bilinear,split[a][b];"
                "[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
         "-loop", "0", GIF_PATH],
        check=True,
    )
    print("GIF gespeichert:", GIF_PATH)
