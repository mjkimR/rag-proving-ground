import asyncio
from abc import ABC, abstractmethod

from rag_eval.schemas import EvalCase, MetricScore


class BaseEvaluator(ABC):
    """
    Abstract base class for all RAG evaluators.
    """

    @abstractmethod
    async def evaluate_case(self, case: EvalCase) -> list[MetricScore]:
        """
        Evaluate a single test case and return list of metric scores.
        """
        pass

    async def evaluate_batch(self, cases: list[EvalCase]) -> list[list[MetricScore]]:
        """
        Evaluate a list of cases. Default implementation evaluates them concurrently.
        """
        tasks = [self.evaluate_case(case) for case in cases]
        return await asyncio.gather(*tasks)
