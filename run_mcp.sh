#!/usr/bin/env bash
# Launcher for the Second Brain MCP server (used by Hermes).
# Sets PYTHONPATH and uses the repo venv Python so no editable install is needed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" -m second_brain.mcp_server
