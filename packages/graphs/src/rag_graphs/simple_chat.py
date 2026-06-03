"""Default Aegra-served LangGraph entrypoint."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from rag_core.ai.models import get_llm_model, get_model_options
from typing_extensions import TypedDict


class GraphConfig(TypedDict):
    model_name: str | None


def _message_content(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)


def respond(state: MessagesState, config: RunnableConfig) -> dict[str, list[AIMessage]]:
    model_name: str | None = config.get("configurable", {}).get("model_name")
    if model_name is not None:
        allowed = get_model_options()["llm_models"]
        if model_name not in allowed:
            raise ValueError(f"Unknown model '{model_name}'. Allowed: {allowed}")

    llm = get_llm_model(model_name)
    messages: list[Any] = state.get("messages", [])
    response = llm.invoke(messages)
    # Ensure we return an AIMessage
    if isinstance(response, AIMessage):
        return {"messages": [response]}
    # If not AIMessage (e.g. BaseMessage), convert or wraps it
    content = _message_content(response)
    return {"messages": [AIMessage(content=content)]}


builder = StateGraph(MessagesState, context_schema=GraphConfig)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)

graph = builder.compile()
