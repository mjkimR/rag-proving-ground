# Parser & Config Sweep Benchmark #1 (Parser & Config Sweep — Lean First Pass)

This document records the first empirical benchmark results of the `RAG Proving Ground`. While the project has integrated various swappable components (5 parsers, sparse/dense/hybrid search, rerank, compression, etc.), **we have never measured which combination actually performs better.** This sweep represents the first empirical measurement and serves as the initial integration of the `rag-eval` evaluation framework with our actual pipeline, replacing previous mock-based setups.

- **Run Date**: 2026-07-08
- **Scope**: 1st Lean Pass — Parser focus, small-scale
- **Test Harness**: `experiments/bench/` (see [7. Reproduction](#7-reproduction) below)
- **Raw Results**: `experiments/bench/results/sweep_results.json`

---

## 1. Summary (TL;DR)

> **"The parser with the best retrieval accuracy produces the worst answers."**
> While `pdf_oxide` achieved perfect retrieval accuracy (MRR 1.000), its generation correctness was the lowest (0.583). The root cause is **over-fragmentation**: it split a single page into 95 chunks (compared to 10 chunks by `pymupdf4llm`). Although this allows the retriever to easily hit relevant text fragments, the highly fragmented context degrades LLM generation quality. This highlights that **retrieval hit rate and generation quality are decoupled metrics.**

Additional findings: `docling` achieved the highest faithfulness but was 14x slower in ingestion, and hybrid search showed no performance benefits over pure dense retrieval in this corpus.

---

## 2. Experimental Setup

### 2.1 Corpus
A small but challenging corpus of **9 documents** (`datasets/pdfs/`) containing difficult layouts, tables, and formulas: FDA Mefloquine drug label, a Goldman Sachs 10-K balance sheet page, two arXiv papers with tables/equations, two veterinary drug SPCs, and a semiconductor datasheet. All documents are single-page excerpts.

### 2.2 Evaluation Set
`experiments/bench/datasets/corpus_eval.json` — **18 questions** (2 per document). The dataset was **synthesized using an LLM based on corpus chunks**, rather than relying on external datasets. Each question includes the ground-truth source document and the gold answer. Because different parsers produce different chunk boundaries, **retrieval is scored at the document level** ("Is the correct source document's chunk present in top-k?").

### 2.3 Experimental Configurations
| Config Name | Parser | Search Mode | Validation Goal |
|---|---|---|---|
| `docling-hybrid` | docling | hybrid (dense+BM25) | High-fidelity layout parser validation |
| `pymupdf4llm-hybrid` | pymupdf4llm | hybrid | Lightweight parser validation |
| `pdf_oxide-hybrid` | pdf_oxide | hybrid | Rust-based high-speed parser validation |
| `docling-dense` | docling | dense only | Validating the necessity of hybrid search |

We used an OFAT (One-Factor-At-a-Time) approach to control variables. Advanced features like reranking, query rewriting, contextual chunking, ColPali, and compression were disabled for this pass.

### 2.4 Metrics
- **Retrieval (Deterministic)**: hit@1/3/5, MRR (Mean Reciprocal Rank) — rank of the ground-truth document.
- **Generation (LLM Judge - `gpt-oss-120b`)**: correctness (against gold answer), faithfulness (adherence to context / hallucination check).
- **Cost/Speed**: query latency, cold ingest time.

### 2.5 Tech Stack
Embedding model: `vllm-embedding` (1024d), generation model: `gpt-oss-20b`, judge model: `gpt-oss-120b` (all routed via LiteLLM proxy). Vector store: Qdrant. The pipeline runs in-process utilizing `rag-core` primitives, bypassing backend APIs or worker orchestration for simplicity.

---

## 3. Results Scorecard

| Config | hit@1 | hit@3 | MRR | correctness | faithfulness | query latency | ingest |
|---|---:|---:|---:|---:|---:|---:|---:|
| docling-hybrid | 0.944 | 1.000 | 0.972 | 0.778 | **0.889** | 1.26s | 🔴 43.6s |
| pymupdf4llm-hybrid | 0.889 | 1.000 | 0.944 | **0.833** | 0.833 | 1.22s | 13.3s |
| pdf_oxide-hybrid | **1.000** | 1.000 | **1.000** | 🔴 0.583 | 0.811 | 1.87s | **3.1s** |
| docling-dense | 0.944 | 1.000 | 0.963 | 0.722 | **0.928** | **1.16s** | 3.2s* |

*Bold* = column best, 🔴 = column worst. hit@5 is omitted as it was 1.000 for all configs.
\* `docling-dense` reused the parser cache generated during `docling-hybrid` execution; its actual cold ingest time is ~44s.

---

## 4. Key Findings

### 4.1 Retrieval easily saturates in a small corpus $\rightarrow$ Focus on Hit@1 and MRR
All configurations achieved hit@3 = hit@5 = 1.000. With only 9 documents in the corpus, a top-3 retrieval almost always contains the correct source. The differentiation lies in the 1st rank (Hit@1); notably, `pdf_oxide` retrieved the correct document at rank 1 for every single test case (MRR 1.000).

### 4.2 [Headline] The parser with the best retrieval accuracy produces the worst answers
`pdf_oxide` achieved perfect retrieval metrics but scored a dismal 0.583 in correctness (a significant gap compared to `pymupdf4llm`'s 0.833). The root cause is over-fragmentation: `pdf_oxide` split a single arXiv page into **95 chunks**, whereas `pymupdf4llm` used **10 chunks**. While tiny, scattered chunks are easily retrieved, passing them to the LLM results in highly fragmented context, causing generation quality to plummet. **Retrieval hit rate and generation quality are decoupled.**

### 4.3 High quality has a time cost: docling achieves best faithfulness but is 14x slower
`docling-dense` achieved the highest faithfulness (0.928), but its cold ingestion took 43.6 seconds for 9 documents compared to 3.1 seconds for `pdf_oxide`. `pymupdf4llm` represents a pragmatic default, striking a good balance at 13.3s ingestion and 0.833 correctness. (Query latency was comparable across all configs at 1.2s to 1.9s.)

### 4.4 Hybrid search does not outperform pure dense search in this corpus
Comparing `docling-hybrid` to `docling-dense`, adding BM25 sparse retrieval provided negligible retrieval gains (MRR 0.972 vs 0.963) and actually reduced faithfulness (0.889 vs 0.928). The dense embeddings alone are sufficient for capturing the queries, while BM25 adds noise and overhead. This should be re-evaluated as the corpus grows and keyword-focused queries are introduced.

---

## 5. Limitations

The main objective of this pass was to **establish and validate the end-to-end evaluation loop** (project-native dataset + live pipeline + E2E metrics), which was successfully achieved. However, the benchmark is not yet statistically robust due to the following limitations:

- **Small sample size**: 9 documents / 18 questions. Retrieval saturated quickly, and small differences of a few points indicate trends rather than statistical significance.
- **LLM Judge Bias/Noise**: Correctness and faithfulness were evaluated using `gpt-oss-120b`. LLM judges introduce noise and may exhibit self-preference bias if they share the same model family as the generator.
- **Single Run**: No repetition or seeding. Judge variance was not quantified with confidence intervals.
- **Disabled features**: Reranking, query rewriting, contextual chunking, ColPali, and compression were bypassed despite being implemented in the codebase.

---

## 6. Next Levers

1. **Validate 4.2**: Run a chunk-size sweep on `pdf_oxide`. If over-fragmentation is indeed the issue, increasing the chunk size should bridge the correctness gap, potentially making the fastest parser the overall winner. (Highest priority)
2. **Expand the corpus**: Increase corpus size from 9 to 30+ documents to prevent retrieval saturation and restore the discriminative power of Hit@K.
3. **Add new dimensions**: Introduce rerankers, query rewriters, and contextual chunking to the sweep configurations.
4. **Multiple runs & confidence intervals**: Perform repetitive runs to quantify LLM judge variance.
5. **ColPali integration**: Currently blocked due to local memory limits. Integrate GPU instances (Kaggle/Colab) to run visual retrieval sweep.

---

## 7. Reproduction

Prerequisites: Run `just up` to start the infrastructure (Qdrant + LiteLLM + parser services). The backend and taskiq workers are not required.

```bash
# 1) Synthesize the evaluation dataset from the corpus (2 questions per document)
uv run python -m experiments.bench.gen_dataset --per-doc 2 --out corpus_eval.json

# 2) Run the sweep configuration
uv run python -m experiments.bench.run_sweep --dataset corpus_eval.json --concurrency 5
```
