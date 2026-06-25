# AGENTS.md - Guide for AI Assistants

Monorepo for building, evaluating, and serving Retrieval-Augmented Generation (RAG) pipelines.

---

## Tooling & Commands

- **SSOT**: `justfile`. Run `just` to list recipes. Inspect it for exact arguments/details. Do not rely on READMEs or comments when they differ from `just`.
- **Recipes**: Most module-scoped recipes accept `all`, `backend`, or `web` (e.g., `just init`, `just lint`, `just check`, `just test`, `just verify`, `just dev backend`).
- **justfile Design**: Keep it thin. Complex logic goes to `scripts/`. Use `just` argument attributes like `[arg("module", pattern="...")]` for finite-choice validation.

---

## Workspace Map

- `apps/backend`: FastAPI & Taskiq worker. Feature code: `app/features`, worker orchestration: `app/worker`.
- `apps/web`: React 19, Vite, TypeScript, CopilotKit UI. Use client under `src/generated/api`.
- `packages/rag-core`: Shared RAG primitives (parsing, chunking, retrieval, embedding, generation, guardrails, adapters, config).
- `packages/graphs`: LangGraph RAG pipelines (within the Aegra server). Depends on `rag-core` (do not duplicate parsing, embedding, or vector-store logic).
- `packages/rag-eval`: Shared evaluation interfaces/runners for RAGAS and DeepEval.
- `infra/services`: Postgres, Qdrant, MinIO, Redis, Docling.
- `infra/models`: Local model-serving runtimes (Ollama, TEI).
- `infra/app`: Docker orchestration placeholder.
- `experiments`, `datasets`: AutoRAG evaluations, baselines, notebooks, cached data.
- `scripts`: Helper scripts called by `justfile`.
- `dev-agents`: Development-time agent harness instructions, hooks, and skills.

---

## Architecture & Code Style

### Python Workspace (`packages/rag-core`, `packages/graphs`, `apps/backend`)

- **Tooling**: `uv` only (never `pip`, `poetry`, `conda`). Python `>=3.13`.
- **Types & Settings**: Strict type hints required for public functions and class attributes. Use `pydantic-settings` `BaseSettings` with `validation_alias` for env var names. Expose cached settings via `@lru_cache` factories.
- **Logging & DB**: Use `loguru` (no `print` in app code). DB migrations: Alembic via `just` (`apps/backend/migrations/versions/`). All database `datetime` columns must be timezone-aware (e.g., using `DateTime(timezone=True)`), and Python code should use `get_current_time()` from `app.common.utils.time_util` rather than naive UTC datetime objects.
- **Config**: `.env` and `models.yaml` are gitignored. Never copy/leak their content into docs, logs, commits, fixtures, or responses. Use `.env.example`/`models.example.yaml` for docs.
- **Adapters**: Parser/vector-store use adapter pattern: `interface.py`, `registry.py`, `factory.py`, `instance.py`, `providers/`. Tests: `packages/rag-core/tests/unit/test_adapters/`.
- **LangGraph**: Defined in `packages/graphs/src/rag_graphs/`.
- **Layering Boundaries**:
  - **No DB in LangGraph**: LangGraph runner must NOT connect directly to databases (Postgres, Qdrant, Redis, etc.) or use their client drivers. Route all retrieval, state checks, and metadata queries through `apps/backend` API endpoints (e.g. `search_multi_knowledge_bases`).
  - **Stateless Utilities**: Stateless operations (`QueryRewriter`, `TreeSummarizer`, `SynonymExpander`, `CitationValidator`) belong to `rag-core` and can run in both `packages/graphs` and `apps/backend`. They must remain stateless (no direct DB handles or local storage).

### Backend (`apps/backend`)

- **Structure**: API routes: `app/features/**/api/`. Business flow: `usecases/`. Persistence: `repos.py`. Transport schemas: `schemas.py`. DB models: `models.py`.
- **Worker**: Entry points: `app/worker/`. Run with `just worker` or `just dev backend`.
- **CPU/GPU Decoupling**: Run heavy CPU/GPU work outside FastAPI/Taskiq. Workers orchestrate; parser engines belong under [infra/services](file:///home/mj/projects/rag-proving-ground/infra/services/docker-compose.yml), model runtimes under [infra/models](file:///home/mj/projects/rag-proving-ground/infra/models/docker-compose.yml), and backend code calls them over network APIs. Never import heavy model/parser frameworks directly in API/worker. `tiktoken` is allowed.
- **API Changes**: Run `just gen-ui-api` and commit generated client changes after backend schema edits.

### Frontend (`apps/web`)

- **Stack**: React 19, TypeScript, Vite, CopilotKit, TanStack Query, Ant Design, generated OpenAPI client.
- **Node/npm**: Node `>=24.0.0`, npm `>=11.0.0` (see `.nvmrc` and `apps/web/package.json`).
- **Markdown**: Use `react-markdown` + `rehype-sanitize` + `remark-gfm`. Never render raw user or LLM HTML without sanitization.
- **API calls**: Use client in `apps/web/src/generated/api/` (no raw `fetch` unless client path missing).
- **Build**: Use `just check web` or `npm --prefix apps/web run build`.

---

## Testing

- Run `just test` (Python tests) or `just test-file <path>` (focused pytest). Pytest roots and async settings live in `pyproject.toml`.
- Add focused tests for new adapters, chunkers, graph nodes, backend use cases, and API behavior.

> [!NOTE]
> Since `asyncio_mode = "auto"` is configured globally in `pyproject.toml`, you do **not** need to add `@pytest.mark.asyncio` to async test functions.

---

## Critical Constraints

1. Never commit secrets, PII, `.env`, or `models.yaml`. Do not copy/paste local config.
2. Never auto-commit via git. Use concise, emoji-free imperative text for commit messages.
3. Run the relevant `just` verification scope before finalizing code changes, or explain why not.
4. Run `just gen-ui-api` and commit client updates after API schema changes.
