@echo off
:: setup_requirements.bat – One-time setup for Merlin on Windows.
:: Run this from the project root before starting the server.
::
:: Usage:
::   setup_requirements.bat

setlocal enableextensions

echo ==========================================================
echo  Merlin – dependency setup
echo ==========================================================

:: ------------------------------------------------------------------
:: 1. Verify Python is available
:: ------------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo and make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo Found: %PY_VERSION%

:: ------------------------------------------------------------------
:: 2. Create virtual environment (only if it doesn't already exist)
:: ------------------------------------------------------------------
if not exist ".venv\" (
    set VENV_MISSING=1
) else if not exist ".venv\Scripts\activate.bat" (
    set VENV_MISSING=1
) else (
    set VENV_MISSING=0
)

if "%VENV_MISSING%"=="1" (
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
    echo Virtual environment already exists – skipping creation.
)

:: ------------------------------------------------------------------
:: 3. Install / upgrade dependencies
:: ------------------------------------------------------------------
echo.
echo Installing dependencies from requirements.txt ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. See output above for details.
    pause
    exit /b 1
)

:: ------------------------------------------------------------------
:: 4. Done – print next steps
:: ------------------------------------------------------------------
echo.
echo ==========================================================
echo  Setup complete!
echo ==========================================================
echo.
echo Next steps:
echo   1. Activate the virtual environment:
echo        .venv\Scripts\activate
echo.
echo   2. Ingest your documents (optional):
echo        python -m app.ingestion.ingest --input .\docs
echo.
echo   3. Start the server:
echo        python main.py
echo        -- or --
echo        uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
echo.
echo   Then open http://127.0.0.1:8000 in your browser.
echo ==========================================================
pause
endlocal
