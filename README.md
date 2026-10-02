# Blender-Animationen

Blender-Animationen per Python-Skript erstellen, lokal oder in Claude-Code-Cloud-Sitzungen.

- `scripts/`: Animationsskripte (Blender-Python-API `bpy`)
- `renders/`: fertige GIFs und Videos
- `.claude/hooks/session-start.sh`: installiert in Cloud-Sitzungen automatisch `bpy` (Blender 4.2 als Python-Modul)

In der Cloud wird mit Cycles auf der CPU gerendert (Eevee braucht eine GPU).

```bash
python3 scripts/wuerfel_rotation.py
```
