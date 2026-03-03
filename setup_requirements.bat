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
:: PIP_EXTRA_ARGS can be overridden in your environment.
:: The default bypasses SSL certificate verification for PyPI hosts, which is
:: required in corporate networks that use self-signed SSL inspection proxies.
:: To use a corporate CA bundle instead, set:
::   set PIP_EXTRA_ARGS=--cert "C:\path\to\corporate-ca.crt"
:: To use standard SSL verification (no proxy), set:
::   set PIP_EXTRA_ARGS=
if not defined PIP_EXTRA_ARGS set "PIP_EXTRA_ARGS=--trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org"
python -m pip install --upgrade pip --quiet %PIP_EXTRA_ARGS%
python -m pip install -r requirements.txt %PIP_EXTRA_ARGS%
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. See output above for details.
    pause
    exit /b 1
)

:: ------------------------------------------------------------------
:: 4. Install llama-cpp-python (required for LLM_MODE=local)
:: ------------------------------------------------------------------
echo.
python -c "import llama_cpp" >nul 2>&1
if errorlevel 1 (
    echo Installing llama-cpp-python ^(--prefer-binary^) ...
    python -m pip install llama-cpp-python --prefer-binary %PIP_EXTRA_ARGS%
    if errorlevel 1 (
        echo.
        echo WARNING: llama-cpp-python installation failed.
        echo          You can install it manually later with:
        echo            pip install llama-cpp-python --prefer-binary
        echo.
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
        echo Edit .env to adjust settings ^(model path, mode, etc.^).
    )
)

:: ------------------------------------------------------------------
:: 6. Done – print next steps
:: ------------------------------------------------------------------
echo.
echo ==========================================================
echo  Setup complete!
echo ==========================================================
echo.
echo To launch the server, simply run:
echo.
echo        start.bat
echo.
echo Or, to start manually:
echo.
echo   1. Activate the virtual environment:
echo        .venv\Scripts\activate
echo.
echo   2. Ingest your documents (optional – done automatically on startup):
echo        python -m app.ingestion.ingest --input .\docs
echo.
echo   3. Start the server:
echo        python main.py
echo.
echo   Then open http://127.0.0.1:8000 in your browser.
echo ==========================================================
pause
endlocal
