# rag-proving-ground

A **Modular RAG Experimentation and Serving Scaffold** — a monorepo for building, evaluating, and serving
Retrieval-Augmented Generation (RAG) pipelines.

## Stack

| Layer                  | Technology                                                                     |
|------------------------|--------------------------------------------------------------------------------|
| API / Worker           | Python 3.13, FastAPI, Taskiq, uvicorn                                          |
| Core library           | `rag-core` — parsers, chunkers, embeddings, retrieval, LLM/reranker wrappers   |
| Graph pipelines        | `rag-graphs` — LangGraph pipelines, served via Aegra (`apps/serve`)            |
| Evaluation             | `rag-eval` — RAGAS / DeepEval evaluation runners                               |
| Frontend               | React 19, Vite, TypeScript, CopilotKit                                         |
| LLM gateway            | LiteLLM proxy (`models.yaml`)                                                  |
| Vector store           | Qdrant                                                                         |
| Metadata DB            | PostgreSQL (pgvector image)                                                    |
| Message broker         | RabbitMQ (Taskiq broker)                                                       |
| Cache / task results   | Redis                                                                          |
| Object storage         | MinIO (S3-compatible)                                                          |
| Document parsing       | Docling Serve, fast-parser                                                     |
| Task runner            | [just](https://github.com/casey/just)                                          |
| Python package manager | [uv](https://github.com/astral-sh/uv)                                          |

---

## Getting Started

### 1. Prerequisites

- [just](https://github.com/casey/just) — install via `scripts/install-just.sh` (Linux) or `scripts/install-just.bat` (
  Windows)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- [Docker](https://docs.docker.com/get-docker/) — for infrastructure services
- Node.js `>=24.0.0` / npm `>=11.0.0` — for the frontend

### 2. Install Dependencies

```bash
just init       # production deps only
just init-dev   # includes dev extras (ruff, pyright, pytest, autorag, etc.)
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and fill in the required API keys
```

Key variables in `.env`:

| Variable                          | Default                    | Description                   |
|-----------------------------------|----------------------------|-------------------------------|
| `LITELLM_BASE_URL`                | `http://localhost:4000/v1` | LiteLLM proxy endpoint        |
| `LITELLM_API_KEY`                 | `sk-local`                 | API key for the proxy         |
| `LITELLM_DEFAULT_LLM_MODEL`       | `gpt-oss-20b`              | Default chat model alias      |
| `LITELLM_DEFAULT_EMBEDDING_MODEL` | `vllm-embedding`           | Default embedding model alias |
| `LITELLM_DEFAULT_RERANKER_MODEL`  | `vllm-reranker`            | Default reranker model alias  |
| `PARSER_PROVIDER`                 | `docling`                  | Active parser adapter         |
| `MINIO_ROOT_USER`                 | `minioadmin`               | MinIO admin user              |
| `MINIO_ROOT_PASSWORD`             | `minioadmin`               | MinIO admin password          |

### 4. Configure Model Routing

```bash
cp models.example.yaml models.yaml
# Edit models.yaml to point to your LLM/embedding/reranker endpoints
```

`models.yaml` is loaded by the LiteLLM proxy and maps logical model aliases (e.g. `gpt-oss-20b`,
`vllm-embedding`) to actual backend endpoints.

### 5. Start Infrastructure

```bash
just up                       # CPU mode — starts the default `basic` profile (all services below)
just up-gpu                   # GPU mode (WSL / Linux)
just up docling fast-parser   # Start with specific profiles only
just down                     # Stop all services
just monitor-up               # Optional: Langfuse monitoring stack (langfuse-web/worker + ClickHouse)
just models-up                # Optional: local model runtimes (Infinity ColPali, LLMLingua)
```

Services started by `just up` (default `basic` profile):

| Service       | Host port         | Description                                          |
|---------------|-------------------|------------------------------------------------------|
| LiteLLM proxy | `14004`           | OpenAI-compatible gateway to LLM backends            |
| MinIO         | `19000` / `19001` | S3-compatible object storage (console at `19001`)    |
| Qdrant        | `16333` / `16334` | Vector store (HTTP / gRPC)                           |
| PostgreSQL    | `15431`           | Metadata DB (pgvector image; litellm/aegra DBs)      |
| Redis         | `16379`           | Task results / cache (RedisInsight at `18001`)       |
| RabbitMQ      | `5672` / `15672`  | Taskiq message broker (management UI at `15672`)     |
| Docling       | `15001`           | Document parsing server (`/docs` · `/ui`)            |
| fast-parser   | `15002`           | Lightweight PDF parsing server                       |

---

## Development

### Monorepo Task Runner (`just`)

This repository uses `just` as the single source of truth for automating workspace development tasks:

```bash
just         # List all available commands

# Lints & Formatting
just lint    # Format and lint Python backend code

# Type Checking
just check          # Run type check for both Python (pyright) and React (tsc)
just check backend  # Run type check for Python backend only
just check web      # Run type check for React web frontend only

# Running Tests
just test                                              # Run module-level default tests
just test backend                                      # Run backend/Python tests
just test-file packages/rag-core/tests/unit/test_adapters/  # Run specific test files or directories

# Running Dev Servers
just dev backend  # Start backend dev services
just dev web      # Start React Vite frontend

# Other Utilities
just kill        # Release ports and kill dangling dev server processes
just gen-ui-api  # Export OpenAPI schema and compile type-safe React SDK
just down        # Stop and clean up all Docker backend services
```

### Frontend (`apps/web`)

```bash
cd apps/web
npm install
just gen-ui-api  # Generate type-safe API client from Python backend
just dev web     # Start React Vite frontend
```

---

## Repository Layout

```
rag-proving-ground/
├── apps/
│   ├── backend/                  # FastAPI app + Taskiq worker (app/features, app/worker)
│   ├── serve/                    # Aegra server entry point (serves rag-graphs pipelines)
│   └── web/                      # React 19 + Vite frontend (generated client in src/generated/api)
├── packages/
│   ├── rag-core/                 # Shared library: parsing, chunking, retrieval, embedding, config
│   │   └── src/rag_core/
│   │       ├── adapters/         # Provider adapters (parser, prompt, vector_store)
│   │       ├── ai/               # LLM / embedding / reranker / sparse model wrappers
│   │       ├── chunkers/         # Recursive, semantic, visual chunking strategies
│   │       ├── compression/      # Context compression (LLMLingua, reranker prefilter)
│   │       ├── embeddings/       # Indexing helpers and embedding config schemas
│   │       ├── parsers/          # Parsed-document IR schemas and renderers
│   │       ├── query_rewrite/    # Query rewriting and synonym expansion
│   │       ├── retrieval/        # Search and rerank orchestration
│   │       ├── summarize/        # Intent routing and tree summarization
│   │       ├── tokenizers/       # Tokenizer wrappers
│   │       └── config.py         # Pydantic settings
│   ├── graphs/                   # LangGraph RAG pipeline definitions (rag-graphs)
│   └── rag-eval/                 # Evaluation interfaces/runners (RAGAS, DeepEval)
├── infra/
│   ├── services/                 # LiteLLM, MinIO, Qdrant, PostgreSQL, Redis, RabbitMQ, parsers
│   │   ├── docker-compose.yml            # (+ .gpu.yml override, .monitor.yml Langfuse stack)
│   │   └── ...
│   ├── models/                   # Local model runtimes (Infinity ColPali, LLMLingua)
│   └── app/                      # Application docker settings placeholder
├── experiments/                  # Evaluation runs (rag-eval demo, sample dataset)
├── datasets/                     # Sample PDFs, parsing cache, batch parse CLI
├── docs/                         # ADRs and architecture docs
├── dev-agents/                   # Development-time agent instructions, hooks, skills
├── scripts/                      # Shell helper scripts called by justfile
├── models.yaml                   # LiteLLM model routing config (gitignored)
├── models.example.yaml           # Model routing template
├── .env.example                  # Environment variable template
├── justfile                      # Task runner (single source of truth)
└── pyproject.toml                # uv workspace root (ruff, pyright, pytest config)
```
