#!/usr/bin/env bash
# start.sh – Launch the Merlin server on Linux / macOS.
# Activates the .venv virtual environment automatically, then runs main.py.
#
# Usage (from anywhere):
#   bash start.sh
#   bash start.sh --host 0.0.0.0 --port 8000
#   bash start.sh --reload

set -euo pipefail

# Always run relative to the directory that contains this script,
# regardless of which directory the user is in when they call it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ------------------------------------------------------------------
# 1. Check that setup_requirements.sh has been run first
# ------------------------------------------------------------------
if [ ! -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    echo ""
    echo "ERROR: Virtual environment not found."
    echo "Please run 'bash setup_requirements.sh' first to install dependencies."
    echo ""
    exit 1
fi

# ------------------------------------------------------------------
# 2. Activate virtual environment
# ------------------------------------------------------------------
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.venv/bin/activate"

# ------------------------------------------------------------------
# 3. Run the server from the project root
# ------------------------------------------------------------------
cd "$SCRIPT_DIR"
python main.py "$@"
