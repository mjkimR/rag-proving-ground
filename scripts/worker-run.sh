#!/usr/bin/env bash
set -euo pipefail

echo "Starting Taskiq worker..."
uv run --directory apps/backend taskiq worker app.worker.main:broker -q kb_ingest:critical -q kb_ingest:high -q kb_ingest:medium -q kb_ingest:low -q kb_ingest:lowest --workers 1
