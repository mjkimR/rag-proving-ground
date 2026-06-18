import re
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
from pydantic import BaseModel, Field

from rag_core.ai.models import get_llm_model


class ExpandedQueries(BaseModel):
    """Pydantic schema for structured query expansion output."""

    queries: list[str] = Field(
        ...,
        description="A list of generated search query variations. Minimum length of list should be greater than or equal to 1.",
    )


class QueryRewriter:
    """Uses LLMs to perform conversational query de-contextualization and query expansion."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name
        self.llm = get_llm_model(model_name)

    async def rewrite(self, query: str, history: list[dict[str, Any]] | None = None) -> str:
        """Rewrites a conversational query based on the conversation history.

        Resolves pronouns, abbreviations, and missing context to produce a standalone search query.
        """
        if not history:
            return query

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a professional search query optimizer. Given the following conversation history and the latest user message, "
                    "rewrite the user message into a standalone, clear search query that incorporates all necessary context (e.g. resolve pronouns like 'it', 'they', 'this'). "
                    "Do NOT answer the question. Only output the rewritten search query. "
                    "If the query is already standalone, return it exactly as is.",
                ),
                ("placeholder", "{history_messages}"),
                ("human", "Latest Message: {query}\nRewritten standalone query:"),
            ]
        )

        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages: list[Any] = []
        for msg in history:
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "human"):
                    messages.append(HumanMessage(content=content))
                elif role in ("assistant", "ai"):
                    messages.append(AIMessage(content=content))
                elif role == "system":
                    messages.append(SystemMessage(content=content))
            else:
                messages.append(msg)

        chain = prompt | self.llm
        try:
            res = await chain.ainvoke({"history_messages": messages, "query": query})

            # Handle LangChain output types safely
            content_raw = res.content if isinstance(res, BaseMessage) else res

            if isinstance(content_raw, list):
                text_parts = []
                for part in content_raw:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(str(part.get("text", "")))
                content = " ".join(text_parts)
            else:
                content = str(content_raw)

            rewritten = content.strip()
            logger.debug(f"Rewrote query: '{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.error(f"Failed to rewrite query: {e}. Returning original.")
            return query

    async def expand(self, query: str, num_queries: int = 3) -> list[str]:
        """Expands a single search query into multiple semantic variations to improve recall."""
        prompt = ChatPromptTemplate.from_template(
            "You are a search query expansion assistant. Generate exactly {num_queries} diverse search query variations "
            "for the following original query to improve RAG search recall. "
            "Ensure the variations cover synonyms, sub-questions, or translation terms.\n"
            "Original Query: {query}"
        )

        try:
            llm_any: Any = self.llm
            if not hasattr(llm_any, "with_structured_output"):
                raise AttributeError("Active LLM does not support with_structured_output.")

            structured_llm = llm_any.with_structured_output(ExpandedQueries)
            chain = prompt | structured_llm
            res = await chain.ainvoke({"query": query, "num_queries": num_queries})

            # Safe parsing
            if isinstance(res, dict):
                queries = res.get("queries") or []
            elif isinstance(res, ExpandedQueries) or hasattr(res, "queries"):
                queries = res.queries
            else:
                queries = []

            # Clean and deduplicate queries, inserting the original at the head
            if query not in queries:
                queries.insert(0, query)
            final_queries = list(dict.fromkeys(queries))[: num_queries + 1]
            logger.debug(f"Expanded query '{query}' into: {final_queries}")
            return final_queries
        except Exception as e:
            logger.warning(f"Structured query expansion failed: {e}. Falling back to text parsing.")
            # Fallback text-based prompt
            fallback_prompt = ChatPromptTemplate.from_template(
                "You are a search query expansion assistant. Generate exactly {num_queries} search query variations for: '{query}'.\n"
                "Write one query per line, without any numbering, bullet points, or introductory text."
            )
            try:
                chain = fallback_prompt | self.llm
                res = await chain.ainvoke({"query": query, "num_queries": num_queries})

                content_raw = res.content if isinstance(res, BaseMessage) else res

                if isinstance(content_raw, list):
                    text_parts = []
                    for part in content_raw:
                        if isinstance(part, str):
                            text_parts.append(part)
                        elif isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(str(part.get("text", "")))
                    content = " ".join(text_parts)
                else:
                    content = str(content_raw)

                lines = [line.strip() for line in content.split("\n") if line.strip()]
                queries = []
                for line in lines:
                    # Strip common prefix numbering/bullets
                    cleaned = re.sub(r"^\d+[\.\)\s-]*", "", line).strip()
                    cleaned = re.sub(r"^[-*+]\s*", "", cleaned).strip()
                    if cleaned:
                        queries.append(cleaned)
                if query not in queries:
                    queries.insert(0, query)
                final_queries = list(dict.fromkeys(queries))[: num_queries + 1]
                return final_queries
            except Exception as exc:
                logger.error(f"Fallback query expansion also failed: {exc}. Returning original query.")
                return [query]
