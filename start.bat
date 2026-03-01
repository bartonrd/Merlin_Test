@echo off
:: start.bat – Launch the Merlin server on Windows.
:: Activates the .venv virtual environment automatically, then runs main.py.
::
:: Usage (from anywhere):
::   start.bat
::   start.bat --host 0.0.0.0 --port 8000
::   start.bat --reload

setlocal enableextensions

:: Always run relative to the directory that contains this script,
:: regardless of which directory the user is in when they call it.
set "SCRIPT_DIR=%~dp0"

:: ------------------------------------------------------------------
:: 1. Check that setup_requirements.bat has been run first
:: ------------------------------------------------------------------
if not exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    echo.
    echo ERROR: Virtual environment not found.
    echo Please run setup_requirements.bat first to install dependencies.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------------
:: 2. Activate virtual environment
:: ------------------------------------------------------------------
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

:: ------------------------------------------------------------------
:: 3. Run the server from the project root
:: ------------------------------------------------------------------
cd /d "%SCRIPT_DIR%"
python main.py %*

endlocal
