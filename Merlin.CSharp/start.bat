@echo off
setlocal

echo =============================================
echo  Merlin C# - Power System Apps Agent
echo =============================================
echo.

REM Check for .NET 8 SDK
dotnet --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: .NET SDK is not installed.
    echo Download from: https://dotnet.microsoft.com/download
    pause
    exit /b 1
)

REM Create data/ and docs/ directories if they don't exist
if not exist "data" mkdir data
if not exist "docs"  mkdir docs

REM Copy appsettings if .env equivalent doesn't exist
if not exist "src\Merlin\appsettings.Local.json" (
    echo Creating appsettings.Local.json from example ...
    copy "src\Merlin\appsettings.json" "src\Merlin\appsettings.Local.json" >nul
    echo   Edit src\Merlin\appsettings.Local.json to configure your LLM and embedding settings.
)

REM Restore and run
echo.
echo Starting Merlin server at http://127.0.0.1:8000 ...
echo.
cd src\Merlin
dotnet run --urls "http://127.0.0.1:8000"

pause
