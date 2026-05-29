#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${DOCLING_SERVE_PORT:-5001}"
STATE_DIR="$ROOT_DIR/.integrations/docling"
PID_FILE="$STATE_DIR/docling-${PORT}.pid"

stopped=0

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping Docling Serve pid=$pid"
    kill "$pid"
    for _ in {1..30}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.2
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "Process did not stop cleanly; forcing pid=$pid"
      kill -9 "$pid"
    fi
    stopped=1
  fi
  rm -f "$PID_FILE"
fi

if [[ "${FORCE_PORT_KILL:-0}" == "1" ]] && command -v lsof >/dev/null 2>&1; then
  port_pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$port_pids" ]]; then
    echo "Stopping process listening on port $PORT: $port_pids"
    kill $port_pids 2>/dev/null || true
    stopped=1
  fi
fi

if [[ "$stopped" == "0" ]]; then
  echo "No Docling Serve process found for port $PORT"
fi
