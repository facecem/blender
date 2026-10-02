#!/bin/bash
# Installiert Blender (bpy) in Claude-Code-Cloud-Sitzungen.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if python3 -c "import bpy" 2>/dev/null; then
  exit 0
fi

pip install -q --root-user-action=ignore -r "$CLAUDE_PROJECT_DIR/requirements.txt"
