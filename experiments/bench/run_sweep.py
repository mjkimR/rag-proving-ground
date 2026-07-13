"""Run the config sweep: for each PipelineConfig, ingest the corpus, answer every eval
case, and score retrieval + generation. Writes a results JSON and prints a scorecard.

Metrics per config:
  - Retrieval (deterministic, doc-level): hit@1/3/5, MRR — "did a chunk from the
    ground-truth source document appear in the top-k, and at what rank?"
  - Latency: mean seconds per query (retrieve + generate).
  - Generation (LLM judge, gpt-oss-120b):
      * correctness  — candidate answer vs the gold ground_truth
      * faithfulness — candidate answer grounded in the retrieved context

Usage:
    uv run python -m experiments.bench.run_sweep --dataset corpus_eval.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from rag_core.ai.models import get_llm_model
from rag_core.retrieval.schemas import RetrievedChunk

from experiments.bench.gen_dataset import _parse_json
from experiments.bench.pipeline import (
    PipelineConfig,
    _extract_text,
    ingest_corpus,
    make_pipeline,
)

CORPUS_DIR = Path(__file__).resolve().parents[2] / "datasets" / "pdfs"
DATA_DIR = Path(__file__).resolve().parent / "datasets"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

JUDGE_MODEL = "gpt-oss-120b"

# Lean sweep: parser axis at hybrid (3) + a dense contrast on the best parser (1).
CONFIGS: list[PipelineConfig] = [
    PipelineConfig(name="docling-hybrid", parser="docling", retrieval_mode="hybrid"),
    PipelineConfig(name="pymupdf4llm-hybrid", parser="pymupdf4llm", retrieval_mode="hybrid"),
    PipelineConfig(name="pdf_oxide-hybrid", parser="pdf_oxide", retrieval_mode="hybrid"),
    PipelineConfig(name="docling-dense", parser="docling", retrieval_mode="dense"),
]

_CORRECTNESS_PROMPT = """You grade a candidate answer against a reference answer for the same question.
Score 0.0 (wrong or missing the key fact) to 1.0 (fully captures the reference's facts).
Return ONLY JSON: {{"score": <float 0..1>}}

QUESTION: {question}
REFERENCE ANSWER: {reference}
CANDIDATE ANSWER: {candidate}"""

_FAITHFULNESS_PROMPT = """You judge whether an answer is grounded in the provided context passages.
Score 0.0 (claims not supported / hallucinated) to 1.0 (every claim supported by the context).
Return ONLY JSON: {{"score": <float 0..1>}}

CONTEXT:
{context}

ANSWER: {answer}"""


def _doc_rank(chunks: list[RetrievedChunk], gold_doc: str) -> int | None:
    """1-based rank of the first retrieved chunk from the gold source document."""
    for i, chunk in enumerate(chunks):
        if chunk.metadata.get("source_doc") == gold_doc:
            return i + 1
    return None


async def _judge(llm: Any, prompt: str) -> float:
    resp = await llm.ainvoke([SystemMessage("You are a strict evaluator."), HumanMessage(content=prompt)])
    parsed = _parse_json(_extract_text(resp.content))
    if not parsed:
        return 0.0
    try:
        return max(0.0, min(1.0, float(parsed.get("score", 0.0))))
    except (TypeError, ValueError):
        return 0.0


async def _score_case(
    case: dict[str, Any],
    pipeline: Any,
    judge_llm: Any,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    async with semaphore:
        gold_doc = case["metadata"]["source_doc"]
        start = time.perf_counter()
        result = await pipeline(case["question"])
        latency = time.perf_counter() - start

        chunks: list[RetrievedChunk] = result["chunks"]
        rank = _doc_rank(chunks, gold_doc)
        context = "\n\n".join(result["contexts"]) or "(no context retrieved)"

        correctness = await _judge(
            judge_llm,
            _CORRECTNESS_PROMPT.format(
                question=case["question"], reference=case["ground_truth"], candidate=result["answer"]
            ),
        )
        faithfulness = await _judge(
            judge_llm, _FAITHFULNESS_PROMPT.format(context=context[:6000], answer=result["answer"])
        )

        return {
            "question": case["question"],
            "gold_doc": gold_doc,
            "rank": rank,
            "latency_sec": latency,
            "correctness": correctness,
            "faithfulness": faithfulness,
            "answer": result["answer"],
        }


def _aggregate(case_results: list[dict[str, Any]]) -> dict[str, float]:
    n = len(case_results)
    ranks = [r["rank"] for r in case_results]

    def hit_at(k: int) -> float:
        return sum(1 for rk in ranks if rk is not None and rk <= k) / n

    mrr = sum((1.0 / rk) if rk else 0.0 for rk in ranks) / n
    return {
        "hit@1": hit_at(1),
        "hit@3": hit_at(3),
        "hit@5": hit_at(5),
        "mrr": mrr,
        "correctness": sum(r["correctness"] for r in case_results) / n,
        "faithfulness": sum(r["faithfulness"] for r in case_results) / n,
        "mean_latency_sec": sum(r["latency_sec"] for r in case_results) / n,
    }


async def run(dataset_name: str, concurrency: int) -> None:
    dataset = json.loads((DATA_DIR / dataset_name).read_text(encoding="utf-8"))
    cases = dataset["cases"]
    pdfs = sorted(CORPUS_DIR.glob("*.pdf"))
    judge_llm = get_llm_model(JUDGE_MODEL, max_tokens=600)
    semaphore = asyncio.Semaphore(concurrency)

    logger.info(f"Sweep: {len(CONFIGS)} configs x {len(cases)} cases over {len(pdfs)} docs")
    summary: dict[str, Any] = {}
    per_config_cases: dict[str, Any] = {}

    for config in CONFIGS:
        logger.info(f"=== config: {config.name} ===")
        try:
            ingest_start = time.perf_counter()
            await ingest_corpus(pdfs, config, wipe=True)
            ingest_sec = time.perf_counter() - ingest_start

            pipeline = make_pipeline(config)
            case_results = await asyncio.gather(*[_score_case(c, pipeline, judge_llm, semaphore) for c in cases])
            agg = _aggregate(case_results)
            agg["ingest_sec"] = ingest_sec
            summary[config.name] = {"config": asdict(config), "metrics": agg}
            per_config_cases[config.name] = case_results
            logger.info(f"[{config.name}] {agg}")
        except Exception as exc:
            logger.opt(exception=exc).error(f"[{config.name}] FAILED: {exc}")
            summary[config.name] = {"config": asdict(config), "error": str(exc)}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "sweep_results.json"
    out.write_text(
        json.dumps(
            {"dataset": dataset_name, "n_cases": len(cases), "summary": summary, "cases": per_config_cases},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _print_scorecard(summary)
    print(f"\nSaved -> {out.relative_to(Path.cwd())}")


def _print_scorecard(summary: dict[str, Any]) -> None:
    cols = ["hit@1", "hit@3", "hit@5", "mrr", "correctness", "faithfulness", "mean_latency_sec", "ingest_sec"]
    header = f"{'config':<22}" + "".join(f"{c:>14}" for c in cols)
    print("\n" + "=" * len(header))
    print("SWEEP SCORECARD")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for name, data in summary.items():
        if "error" in data:
            print(f"{name:<22}{'FAILED: ' + data['error'][:60]:>14}")
            continue
        m = data["metrics"]
        row = f"{name:<22}" + "".join(f"{m[c]:>14.3f}" for c in cols)
        print(row)
    print("=" * len(header))


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the RAG config sweep benchmark.")
    ap.add_argument("--dataset", type=str, default="corpus_eval.json")
    ap.add_argument("--concurrency", type=int, default=5)
    args = ap.parse_args()
    asyncio.run(run(args.dataset, args.concurrency))


if __name__ == "__main__":
    main()
