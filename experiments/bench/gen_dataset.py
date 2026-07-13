"""Generate a project-native evaluation dataset from the PDF corpus.

For each PDF: parse -> chunk -> sample substantive chunks -> ask an LLM to write a
grounded (question, answer) pair for each sampled chunk. Because questions are
generated *from a chunk*, the ground-truth source page falls out automatically and
is parser-agnostic (we key ground truth on `source_doc` + `source_pages`, never on
chunk ids, so it stays fair across parser/chunker variants in the sweep).

Usage:
    uv run python experiments/bench/gen_dataset.py --limit-docs 3 --per-doc 2 --out sample.json
    uv run python experiments/bench/gen_dataset.py --per-doc 3 --out corpus_eval.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from rag_core.adapters.parser.instance import parse_file
from rag_core.ai.models import get_llm_model
from rag_core.chunkers.schemas import ChunkedDocument
from rag_core.chunkers.semantic import chunk_document

from experiments.bench.pipeline import _extract_text

CORPUS_DIR = Path(__file__).resolve().parents[2] / "datasets" / "pdfs"
OUT_DIR = Path(__file__).resolve().parent / "datasets"

GEN_PARSER = "pymupdf4llm"  # single fixed parser for dataset generation
GEN_MODEL = "gpt-oss-120b"  # stronger model for question authoring

_SYSTEM = """You write evaluation questions for a retrieval-augmented-generation benchmark.
Given ONE passage extracted from a document, produce a single realistic question that a
user could ask and that is answered *specifically and only* by this passage, plus a concise
factual answer grounded in the passage.

Rules:
- The question must be answerable from the passage alone, and be specific (name the entity,
  metric, date, or term) — not generic ("what is this about").
- Prefer questions targeting concrete facts: numbers from tables, definitions, named values.
- The answer must be short (1-2 sentences) and directly supported by the passage.
- Return ONLY a JSON object: {"question": "...", "answer": "...", "answerable": true}
- If the passage is boilerplate/navigation/too sparse to ask about, return {"answerable": false}."""


def _is_substantive(chunk: ChunkedDocument) -> bool:
    text = chunk.page_content.strip()
    if len(text) < 200:
        return False
    # skip chunks that are mostly a heading breadcrumb or symbols
    alnum = sum(c.isalnum() for c in text)
    return alnum >= 120


def _sample_chunks(chunks: list[ChunkedDocument], k: int) -> list[ChunkedDocument]:
    substantive = [c for c in chunks if _is_substantive(c)]
    if not substantive:
        return []
    if len(substantive) <= k:
        return substantive
    # deterministic even spread across the document
    step = len(substantive) / k
    return [substantive[int(i * step)] for i in range(k)]


def _parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def _gen_one(llm: Any, chunk: ChunkedDocument, filename: str) -> dict[str, Any] | None:
    pages = chunk.metadata.get("page_numbers") or chunk.page_ids
    user = f"Document: {filename}\nPage(s): {pages}\n\nPassage:\n{chunk.page_content[:2000]}"
    resp = await llm.ainvoke([SystemMessage(_SYSTEM), HumanMessage(content=user)])
    parsed = _parse_json(_extract_text(resp.content))
    if not parsed or not parsed.get("answerable", False):
        return None
    question = (parsed.get("question") or "").strip()
    answer = (parsed.get("answer") or "").strip()
    if not question or not answer:
        return None
    return {
        "question": question,
        "ground_truth": answer,
        "metadata": {
            "source_doc": filename,
            "source_pages": pages,
            "source_chunk_preview": chunk.page_content[:160],
        },
    }


async def generate(limit_docs: int | None, per_doc: int, out_name: str) -> None:
    pdfs = sorted(CORPUS_DIR.glob("*.pdf"))
    if limit_docs:
        pdfs = pdfs[:limit_docs]
    llm = get_llm_model(GEN_MODEL, max_tokens=1200)

    cases: list[dict[str, Any]] = []
    for pdf in pdfs:
        content = pdf.read_bytes()
        parsed = await parse_file(content, filename=pdf.name, content_type="application/pdf", provider=GEN_PARSER)
        chunks = chunk_document(parsed)
        sampled = _sample_chunks(chunks, per_doc)
        logger.info(f"{pdf.name}: {len(chunks)} chunks -> sampling {len(sampled)}")

        results = await asyncio.gather(*[_gen_one(llm, c, pdf.name) for c in sampled])
        kept = [r for r in results if r]
        cases.extend(kept)
        logger.info(f"{pdf.name}: kept {len(kept)}/{len(sampled)} questions")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / out_name
    payload = {"name": out_name.removesuffix(".json"), "cases": cases}
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(f"Wrote {len(cases)} cases from {len(pdfs)} docs -> {out_path}")
    print("\n" + "=" * 60)
    print(f"GENERATED {len(cases)} EVAL CASES -> {out_path.relative_to(Path.cwd())}")
    print("=" * 60)
    for c in cases[:6]:
        print(f"\nQ: {c['question']}")
        print(f"A: {c['ground_truth']}")
        print(f"   [{c['metadata']['source_doc']} p.{c['metadata']['source_pages']}]")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a project-native RAG eval dataset from the PDF corpus.")
    ap.add_argument("--limit-docs", type=int, default=None, help="Only use the first N PDFs (for a quick sample).")
    ap.add_argument("--per-doc", type=int, default=2, help="Questions to attempt per document.")
    ap.add_argument(
        "--out", type=str, default="corpus_eval.json", help="Output filename under experiments/bench/datasets/."
    )
    args = ap.parse_args()
    asyncio.run(generate(args.limit_docs, args.per_doc, args.out))


if __name__ == "__main__":
    main()
