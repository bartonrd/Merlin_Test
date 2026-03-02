#!/usr/bin/env bash
set -e

echo "============================================="
echo " Merlin C# - Power System Apps Agent"
echo "============================================="
echo

# Check for .NET 8 SDK
if ! command -v dotnet &>/dev/null; then
    echo "ERROR: .NET SDK is not installed."
    echo "Download from: https://dotnet.microsoft.com/download"
    exit 1
fi

# Create data/ and docs/ directories if needed
mkdir -p data docs

# Create local settings file on first run
if [ ! -f "src/Merlin/appsettings.Local.json" ]; then
    echo "Creating appsettings.Local.json from example ..."
    cp src/Merlin/appsettings.json src/Merlin/appsettings.Local.json
    echo "  Edit src/Merlin/appsettings.Local.json to configure your LLM and embedding settings."
fi

echo
echo "Starting Merlin server at http://127.0.0.1:8000 ..."
echo

cd src/Merlin
dotnet run --urls "http://127.0.0.1:8000"
