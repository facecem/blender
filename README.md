# Blender-Animationen

Blender-Animationen per Python-Skript erstellen, lokal oder in Claude-Code-Cloud-Sitzungen.

- `scripts/`: Animationsskripte (Blender-Python-API `bpy`)
- `renders/`: fertige GIFs und Videos, dazu `.blend`-Dateien zum Weiterbearbeiten in Blender
- `.claude/hooks/session-start.sh`: installiert in Cloud-Sitzungen automatisch `bpy` (Blender 4.2 als Python-Modul)

In der Cloud wird mit Cycles auf der CPU gerendert (Eevee braucht eine GPU).

```bash
python3 scripts/wuerfel_rotation.py   # rotierender Würfel
python3 scripts/figur_sprung.py       # Figur springt und landet
python3 scripts/ps2_charakter.py      # Alt-Charakter im PS2-Look auf dem Drehteller
python3 scripts/ps2_realistisch.py    # realistischer PS2-Charakter (San-Andreas-Stil), winkt in die Kamera
```

`scripts/ps2_realistisch.py` lädt beim ersten Lauf das freie MakeHuman-Basismodell
mit Skelett aus dem [MPFB2-Repository](https://github.com/makehumancommunity/mpfb2)
nach `assets/makehuman/` (CC0, nicht im Repo eingecheckt).
