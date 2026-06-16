import logging
import math
import sys
from types import ModuleType
from typing import Any, cast

# Fix Ragas 0.4.3 top-level vertexai import issue in environments with langchain-community>=0.4.2
if "langchain_community.chat_models.vertexai" not in sys.modules:
    mock_vertexai = ModuleType("langchain_community.chat_models.vertexai")
    mock_vertexai.ChatVertexAI = object  # type: ignore
    sys.modules["langchain_community.chat_models.vertexai"] = mock_vertexai

from rag_core.ai.models import get_embedding_model, get_llm_model
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from datasets import Dataset
from rag_eval.base import BaseEvaluator
from rag_eval.schemas import EvalCase, MetricScore

logger = logging.getLogger(__name__)


class RagasEvaluator(BaseEvaluator):
    """
    Ragas-based evaluation engine.
    Calculates faithfulness, answer relevance, context precision, and context recall.
    """

    def __init__(self, llm_model_name: str | None = None, embedding_model_name: str | None = None) -> None:
        # Resolve LangChain models
        self.lc_llm = get_llm_model(model_name=llm_model_name)
        self.lc_embeddings = get_embedding_model(model_name=embedding_model_name)

        # Wrap them for Ragas
        self.ragas_llm = LangchainLLMWrapper(self.lc_llm)
        self.ragas_embeddings = LangchainEmbeddingsWrapper(self.lc_embeddings)

        # Configure standard metrics
        self.metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

    async def evaluate_case(self, case: EvalCase) -> list[MetricScore]:
        """
        Evaluate a single case by delegating to evaluate_batch.
        """
        results = await self.evaluate_batch([case])
        return results[0]

    async def evaluate_batch(self, cases: list[EvalCase]) -> list[list[MetricScore]]:
        """
        Evaluate a list of cases in a single batch using Ragas.
        """
        if not cases:
            return []

        # Build dataset for Ragas
        # Ragas expects: question, answer, contexts, ground_truth
        dataset_dict = {
            "question": [case.question for case in cases],
            "answer": [case.answer or "" for case in cases],
            "contexts": [case.contexts or [] for case in cases],
            "ground_truth": [case.ground_truth or "" for case in cases],
        }

        dataset = Dataset.from_dict(dataset_dict)

        # Ragas evaluate is blocking, so we run it in an executor to avoid blocking the event loop.
        import asyncio

        loop = asyncio.get_running_loop()

        try:
            result = await loop.run_in_executor(
                None,
                lambda: evaluate(
                    dataset=dataset, metrics=self.metrics, llm=self.ragas_llm, embeddings=self.ragas_embeddings
                ),
            )

            df = cast(Any, result).to_pandas()

            batch_results = []
            for _, row in df.iterrows():
                case_scores = []
                for m in self.metrics:
                    val = row.get(m.name)
                    score_val = 0.0 if val is None or (isinstance(val, float) and math.isnan(val)) else float(val)
                    case_scores.append(MetricScore(name=m.name, score=score_val))
                batch_results.append(case_scores)

            return batch_results

        except Exception as e:
            logger.error(f"Error during Ragas evaluation batch: {e}", exc_info=True)
            # Return empty or zero scores on exception
            batch_results = []
            for _ in cases:
                case_scores = [MetricScore(name=m.name, score=0.0, reason=str(e)) for m in self.metrics]
                batch_results.append(case_scores)
            return batch_results
