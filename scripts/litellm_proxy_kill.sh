#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LITELLM_PORT:-4000}"
STATE_DIR="$ROOT_DIR/.integrations/litellm"
PID_FILE="$STATE_DIR/litellm-${PORT}.pid"

stop_pid() {
  local pid="$1"
  local label="$2"

  if [[ -z "$pid" ]]; then
    return
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$label is not running pid=$pid"
    return
  fi

  echo "Stopping $label pid=$pid"
  kill "$pid"
  for _ in {1..30}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return
    fi
    sleep 0.2
  done

  if kill -0 "$pid" 2>/dev/null; then
    echo "$label did not stop cleanly; forcing pid=$pid"
    kill -9 "$pid"
  fi
}

stopped=0

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  stop_pid "$pid" "LiteLLM proxy"
  rm -f "$PID_FILE"
  stopped=1
fi

if [[ "${FORCE_PORT_KILL:-0}" == "1" ]] && command -v lsof >/dev/null 2>&1; then
  port_pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$port_pids" ]]; then
    echo "Stopping process listening on port $PORT: $port_pids"
    kill $port_pids 2>/dev/null || true
    sleep 0.5
    remaining_pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$remaining_pids" ]]; then
      echo "Process on port $PORT did not stop cleanly; forcing: $remaining_pids"
      kill -9 $remaining_pids 2>/dev/null || true
    fi
    stopped=1
  fi
fi

if [[ "$stopped" == "0" ]]; then
  echo "No LiteLLM proxy pid file found for port $PORT: $PID_FILE"
  if command -v lsof >/dev/null 2>&1 && lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "A process is listening on port $PORT. Rerun with FORCE_PORT_KILL=1 if you are sure."
  fi
fi
