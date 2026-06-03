#!/usr/bin/env bash
set -euo pipefail

PORTS=(8389 5173 2026)

kill_port() {
    local port="$1"
    local pids=""
    local os_name

    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    fi

    if [ -n "$pids" ]; then
        echo "Terminating processes on port $port: $pids"
        kill $pids 2>/dev/null || true
        return
    fi

    os_name=$(uname -s)
    if [ "$os_name" = "Darwin" ]; then
        echo "No process found on port $port."
        return
    fi

    if command -v fuser >/dev/null 2>&1; then
        fuser -k "$port/tcp" 2>/dev/null || true
        return
    fi

    echo "No process found on port $port."
}

echo "Terminating dangling development processes..."

for port in "${PORTS[@]}"; do
    kill_port "$port"
done

echo "Development servers cleaned up."
