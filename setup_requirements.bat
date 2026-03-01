@echo off
:: setup_requirements.bat – One-shot dependency installer for Merlin (Windows)
::
:: Usage (from the project root):
::   setup_requirements.bat
::
:: What this script does:
::   1. Verifies Python 3.11+ is available.
::   2. Creates a virtual environment in .venv\ (skipped if it already exists).
::   3. Upgrades pip inside the venv.
::   4. Installs all packages listed in requirements.txt.
::   5. Pre-downloads the default sentence-transformers embedding model so
::      the application can run fully offline afterwards.

setlocal enabledelayedexpansion

echo ============================================================
echo  Merlin – Dependency Setup (Windows)
echo ============================================================
echo.

:: ------------------------------------------------------------------
:: 1. Locate Python and verify version >= 3.11
:: ------------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.11 or later from https://www.python.org/downloads/
    echo         and make sure to tick "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
if not defined PY_VER (
    echo [ERROR] Could not determine Python version. Ensure Python is installed correctly.
    pause
    exit /b 1
)
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if %PY_MAJOR% LSS 3 (
    echo [ERROR] Python 3.11+ is required. Found: %PY_VER%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 (
    echo [ERROR] Python 3.11+ is required. Found: %PY_VER%
    pause
    exit /b 1
)

echo [OK] Python %PY_VER% detected.
echo.

:: ------------------------------------------------------------------
:: 2. Create virtual environment (skip if it already exists)
:: ------------------------------------------------------------------
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Virtual environment already exists at .venv\ – skipping creation.
) else (
    echo [INFO] Creating virtual environment in .venv\ ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)
echo.

:: ------------------------------------------------------------------
:: 3. Activate the virtual environment
:: ------------------------------------------------------------------
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.
echo.

:: ------------------------------------------------------------------
:: 4. Upgrade pip
:: ------------------------------------------------------------------
echo [INFO] Upgrading pip ...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [WARN] pip upgrade failed – continuing anyway.
)
echo [OK] pip up to date.
echo.

:: ------------------------------------------------------------------
:: 5. Install project requirements
:: ------------------------------------------------------------------
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found. Run this script from the project root.
    pause
    exit /b 1
)

echo [INFO] Installing packages from requirements.txt ...
echo        (torch + sentence-transformers are large; this may take a few minutes)
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed. See messages above.
    pause
    exit /b 1
)
echo.
echo [OK] All packages installed.
echo.

:: ------------------------------------------------------------------
:: 6. Pre-download the default embedding model for offline use
:: ------------------------------------------------------------------
echo [INFO] Pre-downloading the default embedding model (all-MiniLM-L6-v2) ...
echo        This only happens once; the model is cached in your HuggingFace cache.
echo.
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('[OK] Embedding model ready.')"
if errorlevel 1 (
    echo [WARN] Embedding model download failed – you will need internet access on first run.
)
echo.

:: ------------------------------------------------------------------
:: Done
:: ------------------------------------------------------------------
echo ============================================================
echo  Setup complete!
echo ============================================================
echo.
echo  Next steps:
echo.
echo  1. Activate the virtual environment in any new terminal:
echo         .venv\Scripts\activate
echo.
echo  2. Start llama.cpp with your GGUF model (see README.md).
echo.
echo  3. Ingest your documents:
echo         python -m app.ingestion.ingest --input .\docs --db .\data\db.sqlite --faiss .\data\index.faiss
echo.
echo  4. Start Merlin:
echo         python main.py
echo.
echo  Then open http://localhost:8000 in your browser.
echo.
pause
