# Local Model Smoke Scripts

These scripts are intentionally not named `test_*.py`, so pytest will not collect them by default.
Start the target service first, then run the matching script with `uv run python`.

```bash
just models-up embed
uv run python infra/models/tests/tei_embeddings.py

just models-up rerank
uv run python infra/models/tests/tei_reranker.py

just models-up colpali
uv run python infra/models/tests/infinity_colpali.py
```

Environment overrides:

- `TEI_EMBEDDINGS_URL` defaults to `http://127.0.0.1:7998`
- `TEI_RERANKER_URL` defaults to `http://127.0.0.1:7999`
- `INFINITY_COLPALI_URL` defaults to `http://127.0.0.1:7997`
- `COLPALI_MODEL` defaults to `vidore/colpali-v1.3-merged`
- `MODEL_SMOKE_TIMEOUT` defaults to `60`
