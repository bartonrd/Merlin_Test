#!/usr/bin/env bash
# setup_requirements.sh – One-shot dependency installer for Merlin (Linux / macOS)
#
# Usage (from the project root):
#   bash setup_requirements.sh
#
# What this script does:
#   1. Verifies Python 3.11+ is available.
#   2. Creates a virtual environment in .venv/ (skipped if it already exists).
#   3. Upgrades pip inside the venv.
#   4. Installs all packages listed in requirements.txt.
#   5. Pre-downloads the default sentence-transformers embedding model so
#      the application can run fully offline afterwards.

set -euo pipefail

echo "============================================================"
echo " Merlin – Dependency Setup (Linux / macOS)"
echo "============================================================"
echo

# ------------------------------------------------------------------
# 1. Locate Python 3.11+
# ------------------------------------------------------------------
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=${version%%.*}
        minor=${version#*.}
        minor=${minor%%.*}
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python 3.11 or later was not found."
    echo "        Install it from https://www.python.org/downloads/ or via your"
    echo "        package manager (e.g. 'sudo apt install python3.11')."
    exit 1
fi

echo "[OK] Using $PYTHON ($($PYTHON --version))"
echo

# ------------------------------------------------------------------
# 2. Create virtual environment (skip if it already exists)
# ------------------------------------------------------------------
if [ -f ".venv/bin/activate" ]; then
    echo "[INFO] Virtual environment already exists at .venv/ – skipping creation."
else
    echo "[INFO] Creating virtual environment in .venv/ ..."
    "$PYTHON" -m venv .venv
    echo "[OK] Virtual environment created."
fi
echo

# ------------------------------------------------------------------
# 3. Activate the virtual environment
# ------------------------------------------------------------------
# shellcheck disable=SC1091
source .venv/bin/activate
echo "[OK] Virtual environment activated."
echo

# ------------------------------------------------------------------
# 4. Upgrade pip
# ------------------------------------------------------------------
echo "[INFO] Upgrading pip ..."
python -m pip install --upgrade pip --quiet
echo "[OK] pip up to date."
echo

# ------------------------------------------------------------------
# 5. Install project requirements
# ------------------------------------------------------------------
if [ ! -f "requirements.txt" ]; then
    echo "[ERROR] requirements.txt not found. Run this script from the project root."
    exit 1
fi

echo "[INFO] Installing packages from requirements.txt ..."
echo "       (torch + sentence-transformers are large; this may take a few minutes)"
echo
pip install -r requirements.txt
echo
echo "[OK] All packages installed."
echo

# ------------------------------------------------------------------
# 6. Pre-download the default embedding model for offline use
# ------------------------------------------------------------------
echo "[INFO] Pre-downloading the default embedding model (all-MiniLM-L6-v2) ..."
echo "       This only happens once; the model is cached in your HuggingFace cache."
echo
if python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('[OK] Embedding model ready.')"; then
    :
else
    echo "[WARN] Embedding model download failed – you will need internet access on first run."
fi
echo

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo
echo " Next steps:"
echo
echo " 1. Activate the virtual environment in any new terminal:"
echo "        source .venv/bin/activate"
echo
echo " 2. Start llama.cpp with your GGUF model (see README.md)."
echo
echo " 3. Ingest your documents:"
echo "        python -m app.ingestion.ingest --input ./docs --db ./data/db.sqlite --faiss ./data/index.faiss"
echo
echo " 4. Start Merlin:"
echo "        python main.py"
echo
echo " Then open http://localhost:8000 in your browser."
echo
