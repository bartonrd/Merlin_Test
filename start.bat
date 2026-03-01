@echo off
:: start.bat – One-click setup and launch for Merlin on Windows.
::
:: Run this from anywhere – it will:
::   1. Verify Python is installed
::   2. Create the .venv virtual environment (if missing)
::   3. Install / upgrade Python dependencies from requirements.txt
::   4. Install llama-cpp-python (required for LLM_MODE=local)
::   5. Create .env from .env.example (if .env is missing)
::   6. Start the Merlin server
::
:: Usage:
::   start.bat
::   start.bat --host 0.0.0.0 --port 8000
::   start.bat --reload

setlocal enableextensions

:: Always resolve paths relative to the script's directory.
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ==========================================================
echo  Merlin – setup ^& launch
echo ==========================================================

:: ------------------------------------------------------------------
:: 1. Verify Python is available
:: ------------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: python not found on PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo and make sure "Add Python to PATH" is checked during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo Found: %PY_VERSION%

:: ------------------------------------------------------------------
:: 2. Create virtual environment (once)
:: ------------------------------------------------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

:: ------------------------------------------------------------------
:: 3. Install / upgrade core dependencies
:: ------------------------------------------------------------------
echo.
echo Installing dependencies from requirements.txt ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. See output above for details.
    pause
    exit /b 1
)

:: ------------------------------------------------------------------
:: 4. Install llama-cpp-python (required for LLM_MODE=local)
::    --prefer-binary uses a pre-built wheel; avoids needing a C++ compiler.
:: ------------------------------------------------------------------
echo.
python -c "import llama_cpp" >nul 2>&1
if errorlevel 1 (
    echo Installing llama-cpp-python ^(this may take a moment^) ...
    python -m pip install llama-cpp-python --prefer-binary
    if errorlevel 1 (
        echo.
        echo WARNING: llama-cpp-python installation failed.
        echo          If you are using LLM_MODE=remote or LLM_MODE=none you can ignore this.
        echo          For LLM_MODE=local, please install manually:
        echo            pip install llama-cpp-python --prefer-binary
        echo.
    ) else (
        echo llama-cpp-python installed.
    )
) else (
    echo llama-cpp-python already installed.
)

:: ------------------------------------------------------------------
:: 5. Auto-create .env from .env.example if not present
:: ------------------------------------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo Created .env from .env.example
        echo Default: LLM_MODE=local – edit .env to set your LLM_MODEL_PATH before starting.
        echo Edit .env to change settings ^(e.g. a different model path^).
    )
)

:: ------------------------------------------------------------------
:: 6. Launch the server
:: ------------------------------------------------------------------
echo.
echo ==========================================================
echo  Starting Merlin server ...
echo  Open http://127.0.0.1:8000 in your browser.
echo  Press Ctrl+C to stop.
echo ==========================================================
echo.
python main.py %*

endlocal
