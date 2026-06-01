#!/usr/bin/env bash
set -euo pipefail

echo "Starting FastStream worker..."
uv run --directory apps/backend faststream run app.worker.main:app --workers 1
