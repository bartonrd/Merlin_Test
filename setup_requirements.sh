#!/usr/bin/env bash
# setup_requirements.sh – One-time setup for Merlin on Linux / macOS.
# Run this from the project root before starting the server.
#
# Usage:
#   bash setup_requirements.sh

set -euo pipefail

echo "=========================================================="
echo " Merlin – dependency setup"
echo "=========================================================="

# ------------------------------------------------------------------
# 1. Verify Python is available (prefer python3, fall back to python)
# ------------------------------------------------------------------
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: python3 (or python) not found on PATH."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "Found: $PY_VERSION"

# ------------------------------------------------------------------
# 2. Create virtual environment (only if it doesn't already exist)
# ------------------------------------------------------------------
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/activate" ]; then
    echo ""
    echo "Creating virtual environment in .venv ..."
    $PYTHON -m venv .venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists – skipping creation."
fi

# ------------------------------------------------------------------
# 3. Install / upgrade dependencies
# ------------------------------------------------------------------
echo ""
echo "Installing dependencies from requirements.txt ..."
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

# ------------------------------------------------------------------
# 4. Install llama-cpp-python (required for LLM_MODE=local)
# ------------------------------------------------------------------
echo ""
if ! python -c "import llama_cpp" &>/dev/null 2>&1; then
    echo "Installing llama-cpp-python (--prefer-binary) ..."
    if ! python -m pip install llama-cpp-python --prefer-binary; then
        echo ""
        echo "WARNING: llama-cpp-python installation failed."
        echo "         You can install it manually later with:"
        echo "           pip install llama-cpp-python --prefer-binary"
        echo ""
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
# 6. Done – print next steps
# ------------------------------------------------------------------
echo ""
echo "=========================================================="
echo " Setup complete!"
echo "=========================================================="
echo ""
echo "To launch the server, simply run:"
echo ""
echo "     bash start.sh"
echo ""
echo "Or, to start manually:"
echo ""
echo "  1. Activate the virtual environment:"
echo "       source .venv/bin/activate"
echo ""
echo "  2. Ingest your documents (optional):"
echo "       python -m app.ingestion.ingest --input ./docs"
echo ""
echo "  3. Start the server:"
echo "       python main.py"
echo ""
echo "  Then open http://127.0.0.1:8000 in your browser."
echo "=========================================================="
