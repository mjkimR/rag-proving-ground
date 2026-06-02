#!/usr/bin/env bash
set -euo pipefail

backend_path="apps/backend"
frontend_path="apps/web"

echo "Exporting OpenAPI JSON from Python backend..."
PYTHONPATH="$backend_path" uv run --directory "$backend_path" python -c \
  "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" \
  > "$frontend_path/openapi.json"

echo "Generating API client..."
npm --prefix "$frontend_path" run gen:api

rm -f "$frontend_path/openapi.json"
echo "Frontend API client successfully generated!"
