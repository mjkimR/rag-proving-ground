import asyncio
import logging
from typing import Any, cast

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.models import DeepEvalBaseEmbeddingModel
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from langchain_core.embeddings import Embeddings
from rag_core.ai.models import get_embedding_model, get_llm_model

from rag_eval.base import BaseEvaluator
from rag_eval.schemas import EvalCase, MetricScore

logger = logging.getLogger(__name__)


class LangChainDeepEvalLLM(DeepEvalBaseLLM):
    """
    Adapter to wrap LangChain BaseChatModel for DeepEval metrics.
    """

    def __init__(self, lc_llm: Any) -> None:
        self.lc_llm = lc_llm

    def load_model(self):
        return self.lc_llm

    def generate(self, prompt: str) -> str:
        return str(self.lc_llm.invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        res = await self.lc_llm.ainvoke(prompt)
        return str(res.content)

    def get_model_name(self) -> str:
        return getattr(self.lc_llm, "model_name", "langchain-llm")


class LangChainDeepEvalEmbedding(DeepEvalBaseEmbeddingModel):
    """
    Adapter to wrap LangChain Embeddings for DeepEval metrics.
    """

    def __init__(self, lc_embeddings: Embeddings) -> None:
        self.lc_embeddings = lc_embeddings

    def load_model(self):
        return self.lc_embeddings

    def embed_text(self, text: str) -> list[float]:
        return self.lc_embeddings.embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.lc_embeddings.embed_documents(texts)

    async def a_embed_text(self, text: str) -> list[float]:
        return await self.lc_embeddings.aembed_query(text)

    async def a_embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.lc_embeddings.aembed_documents(texts)

    def get_model_name(self) -> str:
        return "langchain-embeddings"


class DeepEvalEvaluator(BaseEvaluator):
    """
    DeepEval-based evaluation engine.
    Calculates faithfulness and answer relevancy metrics.
    """

    def __init__(self, llm_model_name: str | None = None, embedding_model_name: str | None = None) -> None:
        # Resolve LangChain models
        self.lc_llm = get_llm_model(model_name=llm_model_name)
        self.lc_embeddings = get_embedding_model(model_name=embedding_model_name)

        # Wrap for DeepEval
        self.deepeval_llm = LangChainDeepEvalLLM(self.lc_llm)
        self.deepeval_embeddings = LangChainDeepEvalEmbedding(self.lc_embeddings)

        # Initialize metrics
        self.faithfulness_metric = FaithfulnessMetric(threshold=0.5, model=self.deepeval_llm)
        self.relevancy_metric = AnswerRelevancyMetric(threshold=0.5, model=self.deepeval_llm)

    async def evaluate_case(self, case: EvalCase) -> list[MetricScore]:
        """
        Evaluate a single case using DeepEval metrics.
        """
        # Map EvalCase to DeepEval LLMTestCase
        test_case = LLMTestCase(
            input=case.question,
            actual_output=case.answer or "",
            expected_output=case.ground_truth or "",
            retrieval_context=cast(Any, case.contexts or []),
        )

        scores = []

        # Measure faithfulness
        try:
            await self.faithfulness_metric.a_measure(test_case)
            scores.append(
                MetricScore(
                    name="deepeval_faithfulness",
                    score=float(self.faithfulness_metric.score or 0.0),
                    reason=self.faithfulness_metric.reason,
                )
            )
        except Exception as e:
            logger.error(f"Error measuring DeepEval faithfulness: {e}")
            scores.append(MetricScore(name="deepeval_faithfulness", score=0.0, reason=str(e)))

        # Measure relevancy
        try:
            await self.relevancy_metric.a_measure(test_case)
            scores.append(
                MetricScore(
                    name="deepeval_answer_relevance",
                    score=float(self.relevancy_metric.score or 0.0),
                    reason=self.relevancy_metric.reason,
                )
            )
        except Exception as e:
            logger.error(f"Error measuring DeepEval relevancy: {e}")
            scores.append(MetricScore(name="deepeval_answer_relevance", score=0.0, reason=str(e)))

        return scores

    async def evaluate_batch(self, cases: list[EvalCase]) -> list[list[MetricScore]]:
        """
        Evaluate a list of cases. Evaluates them concurrently to speed up execution.
        """
        tasks = [self.evaluate_case(case) for case in cases]
        return list(await asyncio.gather(*tasks))
