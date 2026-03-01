#!/usr/bin/env bash
# start.sh – One-click setup and launch for Merlin on Linux / macOS.
#
# Run this from anywhere – it will:
#   1. Verify Python is installed
#   2. Create the .venv virtual environment (if missing)
#   3. Install / upgrade Python dependencies from requirements.txt
#   4. Install llama-cpp-python (required for LLM_MODE=local)
#   5. Create .env from .env.example (if .env is missing)
#   6. Start the Merlin server
#
# Usage:
#   bash start.sh
#   bash start.sh --host 0.0.0.0 --port 8000
#   bash start.sh --reload

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo " Merlin – setup & launch"
echo "=========================================================="

# ------------------------------------------------------------------
# 1. Verify Python is available
# ------------------------------------------------------------------
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo ""
    echo "ERROR: python3 (or python) not found on PATH."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "Found: $PY_VERSION"

# ------------------------------------------------------------------
# 2. Create virtual environment (once)
# ------------------------------------------------------------------
if [ ! -f ".venv/bin/activate" ]; then
    echo ""
    echo "Creating virtual environment in .venv ..."
    $PYTHON -m venv .venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# ------------------------------------------------------------------
# 3. Install / upgrade core dependencies
# ------------------------------------------------------------------
echo ""
echo "Installing dependencies from requirements.txt ..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

# ------------------------------------------------------------------
# 4. Install llama-cpp-python (required for LLM_MODE=local)
#    --prefer-binary uses a pre-built wheel; avoids needing a C compiler.
# ------------------------------------------------------------------
echo ""
if ! python -c "import llama_cpp" &>/dev/null 2>&1; then
    echo "Installing llama-cpp-python (this may take a moment) ..."
    if ! python -m pip install llama-cpp-python --prefer-binary; then
        echo ""
        echo "WARNING: llama-cpp-python installation failed."
        echo "         If you are using LLM_MODE=remote or LLM_MODE=none you can ignore this."
        echo "         For LLM_MODE=local, please install manually:"
        echo "           pip install llama-cpp-python --prefer-binary"
        echo ""
    else
        echo "llama-cpp-python installed."
    fi
else
    echo "llama-cpp-python already installed."
fi

# ------------------------------------------------------------------
# 5. Auto-create .env from .env.example if not present
# ------------------------------------------------------------------
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from .env.example"
    echo "Edit .env to adjust settings (model path, mode, etc.)."
fi

# ------------------------------------------------------------------
# 6. Launch the server
# ------------------------------------------------------------------
echo ""
echo "=========================================================="
echo " Starting Merlin server ..."
echo " Open http://127.0.0.1:8000 in your browser."
echo " Press Ctrl+C to stop."
echo "=========================================================="
echo ""
python main.py "$@"
