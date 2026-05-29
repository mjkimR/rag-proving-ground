## LiteLLM proxy

Create a local `.env` from the example and fill in the API keys referenced by
`models.yaml`.

```bash
cp .env.example .env
vi .env
```

Start or restart the proxy:

```bash
scripts/litellm_proxy.sh
```

The script loads `.env`, stops the previous process for the same port, and runs:

```bash
litellm --config models.yaml --port 4000
```

Logs and the pid file are written under `.integrations/litellm/`.

Stop the proxy started for the same port:

```bash
scripts/litellm_proxy_kill.sh
```

If port `4000` is occupied by a process that was not started from this script,
the script exits instead of killing it. To force-stop the port owner:

```bash
FORCE_PORT_KILL=1 scripts/litellm_proxy.sh
```

The same force-stop option is available for the kill script:

```bash
FORCE_PORT_KILL=1 scripts/litellm_proxy_kill.sh
```

## Docling Serve

Docling is kept in a separate uv project under `services/docling/` so parser
dependencies do not have to live in the main RAG API environment.

Start or restart the local Docling API:

```bash
scripts/docling_serve.sh
```

The first run creates `services/docling/.venv`, installs `docling-serve[ui]`,
and may download Docling model artifacts into Docling's default cache. Logs and
pid files are written under `.integrations/docling/`.

Default endpoints:

```text
API:  http://127.0.0.1:5001
Docs: http://127.0.0.1:5001/docs
UI:   http://127.0.0.1:5001/ui
```

Stop the service:

```bash
scripts/docling_serve_kill.sh
```

Useful overrides:

```bash
DOCLING_SERVE_PORT=5011 scripts/docling_serve.sh
DOCLING_SERVE_LOAD_MODELS_AT_BOOT=1 scripts/docling_serve.sh
DOCLING_SERVE_MAX_SYNC_WAIT=300 scripts/docling_serve.sh
DOCLING_SERVE_ARTIFACTS_PATH=/path/to/preloaded/models scripts/docling_serve.sh
```

Smoke test after the server is up:

```bash
curl -X POST 'http://127.0.0.1:5001/v1/convert/source' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"sources":[{"kind":"http","url":"https://arxiv.org/pdf/2501.17887"}]}'
```
