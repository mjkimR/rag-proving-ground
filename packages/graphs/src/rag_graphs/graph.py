"""Default Aegra-served LangGraph entrypoint."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, MessagesState, StateGraph


def _message_content(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)


def respond(state: MessagesState) -> dict[str, list[AIMessage]]:
    messages: list[Any] = state.get("messages", [])
    latest = _message_content(messages[-1]) if messages else ""
    content = f"Received by rag-proving-ground Aegra agent: {latest}"
    return {"messages": [AIMessage(content=content)]}


builder = StateGraph(MessagesState)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)

graph = builder.compile()
