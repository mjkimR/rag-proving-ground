import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from rag_eval.base import BaseEvaluator
from rag_eval.schemas import EvalCase, EvalCaseResult, EvalDataset, EvalRunResult

logger = logging.getLogger(__name__)

# Type definition for RAG pipeline callable
# Can return:
# - tuple[str, list[str]]: (answer, contexts)
# - dict[str, Any]: containing "answer" (or "response") and "contexts" (or "references")
PipelineCallable = Callable[[str], Awaitable[tuple[str, list[str]] | dict[str, Any]]]


class EvaluationRunner:
    """
    Coordinates executing the RAG pipeline on an evaluation dataset
    and running the evaluators to compute metrics.
    """

    def __init__(self, evaluators: list[BaseEvaluator]) -> None:
        self.evaluators = evaluators

    async def run_pipeline_on_case(self, case: EvalCase, pipeline: PipelineCallable) -> EvalCase:
        """
        Run the RAG pipeline on a single test case and record answer, contexts, and latency.
        """
        try:
            res = await pipeline(case.question)

            # Parse response format
            if isinstance(res, tuple):
                answer, contexts = res
            elif isinstance(res, dict):
                answer = res.get("answer") or res.get("response") or ""
                contexts = res.get("contexts") or res.get("references") or []
                # If references are dictionaries (e.g., retrieved chunk metadata), extract page_content/content
                if contexts and isinstance(contexts[0], dict):
                    contexts = [c.get("content") or c.get("page_content") or "" for c in contexts]
            else:
                raise ValueError(f"Unsupported pipeline response type: {type(res)}")

            case.answer = answer
            case.contexts = contexts

        except Exception as e:
            logger.error(f"Error running pipeline on case '{case.question}': {e}", exc_info=True)
            case.answer = f"ERROR: {e}"
            case.contexts = []

        return case

    async def run(
        self,
        dataset: EvalDataset,
        pipeline: PipelineCallable,
        output_path: str | Path | None = None,
        concurrency_limit: int = 3,
    ) -> EvalRunResult:
        """
        Execute RAG pipeline on the dataset, evaluate with metrics, and return aggregated results.
        """
        logger.info(f"Starting evaluation run for dataset '{dataset.name}' with {len(dataset.cases)} cases.")
        total_start = time.perf_counter()

        # 1. Run pipeline on all cases (with concurrency control)
        semaphore = asyncio.Semaphore(concurrency_limit)

        async def run_with_semaphore(case: EvalCase) -> tuple[EvalCase, float]:
            async with semaphore:
                case_start = time.perf_counter()
                updated_case = await self.run_pipeline_on_case(case, pipeline)
                latency = time.perf_counter() - case_start
                return updated_case, latency

        # Run pipeline
        run_tasks = [run_with_semaphore(case) for case in dataset.cases]
        pipeline_results = await asyncio.gather(*run_tasks)

        # 2. Evaluate all cases using each evaluator
        logger.info("Pipeline runs completed. Starting evaluator runs.")

        eval_cases = [res[0] for res in pipeline_results]
        latencies = [res[1] for res in pipeline_results]

        # Initialize results list
        case_results = [
            EvalCaseResult(case=case, metrics=[], latency_sec=latency, success=True)
            for case, latency in zip(eval_cases, latencies, strict=True)
        ]

        for evaluator in self.evaluators:
            evaluator_name = evaluator.__class__.__name__
            logger.info(f"Running evaluator: {evaluator_name}")
            try:
                batch_scores = await evaluator.evaluate_batch(eval_cases)
                for case_res, scores in zip(case_results, batch_scores, strict=True):
                    if case_res.success:
                        case_res.metrics.extend(scores)
            except Exception as e:
                logger.error(f"Failed evaluator {evaluator_name}: {e}", exc_info=True)
                for case_res in case_results:
                    case_res.success = False
                    case_res.error_message = f"{evaluator_name} failed: {e}"

        total_latency = time.perf_counter() - total_start

        # 3. Aggregated metrics summary
        metric_sums: dict[str, float] = {}
        metric_counts: dict[str, int] = {}

        for r in case_results:
            if not r.success:
                continue
            for m in r.metrics:
                metric_sums[m.name] = metric_sums.get(m.name, 0.0) + m.score
                metric_counts[m.name] = metric_counts.get(m.name, 0) + 1

        summary = {
            name: (metric_sums[name] / metric_counts[name]) if metric_counts[name] > 0 else 0.0 for name in metric_sums
        }

        run_result = EvalRunResult(
            dataset_name=dataset.name,
            results=case_results,
            summary=summary,
            timestamp=datetime.utcnow(),
            total_latency_sec=total_latency,
        )

        # 4. Save output to file if specified
        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(run_result.model_dump_json(indent=2))
            logger.info(f"Evaluation results successfully saved to {output_path}")

        return run_result
