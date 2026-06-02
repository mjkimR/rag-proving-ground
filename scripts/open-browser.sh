#!/usr/bin/env bash
set -euo pipefail

URL="http://localhost:5173"

echo "Opening $URL in browser..."

if grep -qEi "(Microsoft|WSL)" /proc/version &> /dev/null; then
    # In WSL
    if command -v powershell.exe &> /dev/null; then
        powershell.exe -NoProfile -Command "Start-Process '${URL}'"
    else
        cmd.exe /c start "" "${URL}"
    fi
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open "${URL}"
elif command -v open &> /dev/null; then
    # macOS
    open "${URL}"
else
    echo "Could not find a suitable command to open browser automatically."
    echo "Please open your browser and visit: ${URL}"
fi
