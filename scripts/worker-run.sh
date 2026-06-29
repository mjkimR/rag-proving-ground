#!/usr/bin/env bash
set -euo pipefail

echo "Starting Taskiq worker..."
uv run --directory apps/backend taskiq worker app.worker.main:broker --workers 1
