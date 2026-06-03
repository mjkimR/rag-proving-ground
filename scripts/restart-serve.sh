#!/usr/bin/env bash
# scripts/restart-serve.sh — Restart the Aegra serving container to reflect code changes
set -euo pipefail

CONTAINER_NAME="rag-serve"
PORT=2026

# Check if the container exists
if ! docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "Error: The '${CONTAINER_NAME}' container does not exist." >&2
    echo "Please start the serve profile first using 'just up serve' or 'just up-gpu serve'." >&2
    exit 1
fi

# Check if the container is running
if ! docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "Warning: The '${CONTAINER_NAME}' container exists but is not running."
    echo "Starting '${CONTAINER_NAME}' container..."
    docker start "${CONTAINER_NAME}"
else
    echo "Restarting '${CONTAINER_NAME}' container to reflect graph/code changes..."
    docker restart "${CONTAINER_NAME}"
fi

echo "Waiting for Aegra serving endpoint to become healthy..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -sf "http://localhost:${PORT}/health" > /dev/null 2>&1; then
        echo "Aegra serving container '${CONTAINER_NAME}' is healthy and ready!"
        exit 0
    fi
    sleep 0.5
    attempt=$((attempt + 1))
done

echo "Warning: Container restarted, but health check (http://localhost:${PORT}/health) did not pass within timeout." >&2
echo "You can check logs with: docker logs ${CONTAINER_NAME}" >&2
exit 1
