from enum import StrEnum
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
from pydantic import BaseModel, Field

from rag_core.ai.models import get_llm_model
from rag_core.config import get_litellm_settings


class SummarizeStrategy(StrEnum):
    FULL_TREE = "FULL_TREE"
    TARGETED_RAG = "TARGETED_RAG"


class IntentClassification(BaseModel):
    """Pydantic schema for structured intent classification output."""

    strategy: SummarizeStrategy = Field(
        ...,
        description="The summarization strategy to use based on the user's intent. "
        "Use FULL_TREE if the user wants an overall summary, high-level outline, or structural analysis of the entire document. "
        "Use TARGETED_RAG if the user is asking about specific facts, details, or a particular topic within the document.",
    )


class SummarizeIntentClassifier:
    """Classifies user queries to determine the best summarization strategy."""

    def __init__(self, model_name: str | None = None) -> None:
        """Initializes the SummarizeIntentClassifier.

        Args:
            model_name: Optional explicit name of the model. If not provided,
              falls back to the default LLM from settings.
        """
        self.model_name = model_name or get_litellm_settings().default_llm_model
        self.llm = get_llm_model(self.model_name)
        logger.info(f"Initialized SummarizeIntentClassifier using model '{self.model_name}'")

    async def classify(self, query: str) -> SummarizeStrategy:
        """Classifies the user query intent using LLM-as-a-judge with structured output."""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert AI assistant that routes user queries to the optimal summarization strategy.\n"
                    "Analyze the user's question and select the most appropriate strategy:\n"
                    "- FULL_TREE: If the user asks for a comprehensive summary, the main points of the entire document, "
                    "a high-level structure, or an overall overview of the document.\n"
                    "- TARGETED_RAG: If the user asks about a specific fact, a particular topic, details, or a factual "
                    "question that requires finding specific parts of the document.",
                ),
                ("human", "User query: {query}"),
            ]
        )

        try:
            llm_any: Any = self.llm
            if not hasattr(llm_any, "with_structured_output"):
                raise AttributeError("Active LLM does not support with_structured_output.")

            structured_llm = llm_any.with_structured_output(IntentClassification)
            chain = prompt | structured_llm
            res = await chain.ainvoke({"query": query})

            # Safe parsing of response
            if isinstance(res, dict):
                strategy_val = res.get("strategy")
            elif isinstance(res, IntentClassification) or hasattr(res, "strategy"):
                strategy_val = res.strategy
            else:
                strategy_val = None

            if strategy_val in (SummarizeStrategy.FULL_TREE, SummarizeStrategy.TARGETED_RAG):
                logger.debug(f"Classified query '{query}' as strategy '{strategy_val}'")
                return SummarizeStrategy(strategy_val)

            logger.warning(f"Classification returned unexpected output: {res}. Falling back to default.")
        except Exception as e:
            logger.warning(f"Structured intent classification failed: {e}. Falling back to text-based classification.")

        # Fallback text completion classification
        logger.info("Executing fallback text-based intent classification.")

        fallback_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a routing assistant. Classify the user query into either 'FULL_TREE' or 'TARGETED_RAG'.\n"
                    "Respond with exactly one of those two words and nothing else.",
                ),
                ("human", "User query: {query}"),
            ]
        )
        try:
            chain = fallback_prompt | self.llm
            res = await chain.ainvoke({"query": query})
            content = str(res.content if hasattr(res, "content") else res).strip().upper()
            if "FULL_TREE" in content:
                logger.debug(f"Fallback classification classified query '{query}' as strategy 'FULL_TREE'")
                return SummarizeStrategy.FULL_TREE
            if "TARGETED_RAG" in content:
                logger.debug(f"Fallback classification classified query '{query}' as strategy 'TARGETED_RAG'")
                return SummarizeStrategy.TARGETED_RAG

            logger.warning(
                f"Fallback classification returned ambiguous content: '{content}'. "
                f"Defaulting to '{SummarizeStrategy.TARGETED_RAG}'."
            )
        except Exception as fallback_err:
            logger.error(f"Fallback classification failed: {fallback_err}. Defaulting to TARGETED_RAG.")

        # Final default fallback
        return SummarizeStrategy.TARGETED_RAG
