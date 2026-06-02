#!/usr/bin/env bash
set -euo pipefail
TOOL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:?usage: install.sh <repo-path>}"
ln -sf "$TOOL_DIR/hooks/pre-push" "$REPO/.git/hooks/pre-push"
chmod +x "$TOOL_DIR/hooks/pre-push"
echo "Installed pre-push hook in $REPO"
cat <<MSG

Add to ~/.claude/settings.json "hooks"."SessionStart" to enable PULL on session start:
  { "type": "command",
    "command": "PYTHONPATH=$TOOL_DIR/src python3 -m beads_gh_sync.cli pull --repo \"\$(pwd)\"" }
MSG
