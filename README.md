# rag-proving-ground

A **Modular RAG Experimentation and Serving Scaffold** — a monorepo for building, evaluating, and serving
Retrieval-Augmented Generation (RAG) pipelines.

## Stack

| Layer                  | Technology                                                        |
|------------------------|-------------------------------------------------------------------|
| API                    | Python 3.13, FastAPI, uvicorn                                     |
| Core library           | `rag-core` — parsers, chunkers, embeddings, LLM/reranker wrappers |
| Graph pipelines        | `rag-graphs` — LangGraph-based RAG pipeline definitions           |
| Frontend               | React 19, Vite, TypeScript, CopilotKit                            |
| LLM gateway            | LiteLLM proxy (`models.yaml`)                                     |
| Object storage         | MinIO (S3-compatible)                                             |
| Document parsing       | Docling Serve                                                     |
| Task runner            | [just](https://github.com/casey/just)                             |
| Python package manager | [uv](https://github.com/astral-sh/uv)                             |

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
just up                    # CPU mode — starts Docling + LiteLLM + MinIO
just up-gpu                # GPU mode (WSL / Linux)
just up docling marker     # Start with additional optional profiles
just down                  # Stop all services
```

Services started by `just up`:

| Service       | Port            | Description                                      |
|---------------|-----------------|--------------------------------------------------|
| LiteLLM proxy | `4000`          | OpenAI-compatible gateway to LLM backends        |
| MinIO         | `9000` / `9001` | S3-compatible object storage (console at `9001`) |
| Docling       | `5001`          | Document parsing server (`/docs` · `/ui`)        |

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
just test                                                   # Run all pytest tests
just test packages/rag-core/src/tests/unit/test_adapters/  # Run specific test files or directories

# Running Dev Servers
just dev-backend  # Start FastAPI backend in reloading mode (port 8389)
just dev-web      # Start React Vite frontend (port 5173)

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
just dev-web     # Start React Vite frontend (port 5173)
```

---

## Repository Layout

```
rag-proving-ground/
├── apps/
│   ├── api/                      # FastAPI application (parsing/chunking endpoints)
│   │   └── app/main.py
│   └── web/                      # React 19 + Vite frontend
│       └── src/
├── packages/
│   ├── rag-core/                 # Shared library: parsers, chunkers, embeddings, AI, config
│   │   └── src/rag_core/
│   │       ├── adapters/         # Provider adapters (e.g., Docling parser adapter)
│   │       ├── ai/               # LLM / reranker wrappers
│   │       ├── chunkers/         # Recursive and semantic chunking strategies
│   │       ├── embeddings/       # Embedding model wrappers
│   │       ├── parsers/          # Document parser interfaces and schemas
│   │       ├── vector_db/        # Vector store utilities
│   │       └── config.py         # Pydantic settings (LiteLLM, Parser, HTTP)
│   └── graphs/                   # LangGraph RAG pipeline definitions
│       └── src/rag_graphs/
├── infra/
│   ├── services/                 # Databases, vector store, redis, minio, docling compose settings
│   │   ├── docker-compose.yml
│   │   └── docker-compose.gpu.yml
│   ├── models/                   # Local model runtimes (Ollama, TEI)
│   │   └── docker-compose.yml
│   └── app/                      # Application docker settings placeholder
│       └── docker-compose.yml
├── experiments/
│   ├── autorag/                  # AutoRAG evaluation configs and results
│   ├── baselines/                # Baseline pipeline scripts
│   └── notebooks/                # Jupyter notebooks
├── scripts/                      # Shell helper scripts
├── models.yaml                   # LiteLLM model routing config (gitignored)
├── models.example.yaml           # Model routing template
├── .env.example                  # Environment variable template
├── justfile                      # Task runner (single source of truth)
└── pyproject.toml                # uv workspace root (ruff, pyright, pytest config)
```
