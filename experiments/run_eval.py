#!/usr/bin/env python
import argparse
import asyncio
import sys
from pathlib import Path

# Add project packages to sys.path if not running in uv workspace environment
sys.path.append(str(Path(__file__).parent.parent / "packages" / "rag-core" / "src"))
sys.path.append(str(Path(__file__).parent.parent / "packages" / "rag-eval" / "src"))

from rag_eval import (
    DeepEvalEvaluator,
    EvalCase,
    EvalDataset,
    EvaluationRunner,
    RagasEvaluator,
)


# Mock pipeline for testing the evaluation runner without requiring active database/embeddings
async def mock_rag_pipeline(question: str) -> dict:
    print(f"[Pipeline] Processing question: '{question}'...")
    await asyncio.sleep(0.5)  # Simulate network latency

    if "core components" in question.lower():
        return {
            "answer": "RAG Proving Ground consists of core components: parsing, chunking, retrieval, generation, and evaluation.",
            "contexts": [
                "The system layout defines packages like rag-core and graphs, and apps like backend and web.",
                "It serves as a modular scaffold for retrieval-augmented generation pipelines.",
            ],
        }
    elif "설계 원칙" in question:
        return {
            "answer": "RAG Proving Ground의 핵심 설계 원칙은 비동기 파이프라인, 모듈화 및 확장성, 점진적 고도화입니다.",
            "contexts": [
                "핵심 설계 원칙: 비동기식 파이프라인(Asynchronous Ingestion), 모듈화 및 확장성(Modularity & Extensibility), 점진적 고도화(Incremental Complexity)"
            ],
        }
    else:
        return {"answer": "This is a generic mock answer.", "contexts": ["This is generic mock retrieved context."]}


async def main():
    parser = argparse.ArgumentParser(description="RAG Proving Ground Evaluation Runner CLI")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(Path(__file__).parent / "sample_dataset.json"),
        help="Path to the evaluation dataset JSON file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path(__file__).parent / "results" / "eval_results.json"),
        help="Path to save evaluation results",
    )
    parser.add_argument(
        "--evaluator",
        type=str,
        choices=["ragas", "deepeval", "all"],
        default="all",
        help="The evaluator engine to use (default: all)",
    )

    args = parser.parse_args()

    # 1. Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {args.dataset}")
        sys.exit(1)

    import json

    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    dataset = EvalDataset(name=data.get("name", "evaluation_run"), cases=[EvalCase(**c) for c in data.get("cases", [])])

    print(f"Loaded dataset '{dataset.name}' with {len(dataset.cases)} cases.")

    # 2. Setup evaluators
    evaluators = []
    if args.evaluator in ("ragas", "all"):
        print("Initializing Ragas Evaluator...")
        evaluators.append(RagasEvaluator())
    if args.evaluator in ("deepeval", "all"):
        print("Initializing DeepEval Evaluator...")
        evaluators.append(DeepEvalEvaluator())

    runner = EvaluationRunner(evaluators=evaluators)

    # 3. Execute evaluation (using mock pipeline for validation)
    print("Running evaluation pipeline...")
    results = await runner.run(dataset=dataset, pipeline=mock_rag_pipeline, output_path=args.output)

    # 4. Print Summary
    print("\n" + "=" * 40)
    print("EVALUATION COMPLETED SUCCESSFULLY")
    print(f"Total Latency: {results.total_latency_sec:.2f} seconds")
    print("Aggregated Scores:")
    for metric, score in results.summary.items():
        print(f" - {metric}: {score:.4f}")
    print("=" * 40)
    print(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
