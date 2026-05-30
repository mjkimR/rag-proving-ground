#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

target=$(resolve_module "${1:-all}")

PID_WEB=""
PID_BACKEND=""

if should_run "$target" "web"; then
    path=$(resolve_module_path "web")
    echo "Starting React frontend ($path)..."
    npm --prefix "$path" run dev &
    PID_WEB=$!
fi

if should_run "$target" "backend"; then
    path=$(resolve_module_path "backend")
    echo "Starting FastAPI backend ($path)..."
    uv run --directory "$path" uvicorn app.main:create_app --port 8389 --reload &
    PID_BACKEND=$!
fi

# Set up clean up for processes on script termination
cleanup() {
    echo "Stopping development servers..."
    [ -n "$PID_WEB" ] && kill "$PID_WEB" 2>/dev/null || true
    [ -n "$PID_BACKEND" ] && kill "$PID_BACKEND" 2>/dev/null || true
}

PIDS=()
[ -n "$PID_WEB" ] && PIDS+=("$PID_WEB")
[ -n "$PID_BACKEND" ] && PIDS+=("$PID_BACKEND")

if [ ${#PIDS[@]} -ne 0 ]; then
    trap cleanup SIGINT SIGTERM EXIT
    wait -n "${PIDS[@]}"
    echo "One of the background components stopped. Shutting down remaining servers..."
fi
