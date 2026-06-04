"""Message normalization helpers for provider-compatible LLM calls."""

from typing import Any

from langchain_core.messages import BaseMessage

HIDDEN_CONTENT_BLOCK_TYPES = {"thinking", "reasoning"}


def message_content(message: BaseMessage) -> str:
    return visible_content(message.content)


def visible_content(content: Any) -> str:
    accumulator: list[str] = []

    def _collect(item: Any) -> None:
        if isinstance(item, str):
            accumulator.append(item)
        elif isinstance(item, list):
            for sub_item in item:
                _collect(sub_item)
        elif isinstance(item, dict):
            block_type = item.get("type")
            if isinstance(block_type, str) and block_type in HIDDEN_CONTENT_BLOCK_TYPES:
                return
            text = item.get("text")
            if isinstance(text, str):
                accumulator.append(text)
                return
            nested = item.get("content")
            if isinstance(nested, str | list | dict):
                _collect(nested)

    _collect(content)
    return "".join(accumulator)


def sanitize_messages_for_llm(messages: list[Any]) -> list[Any]:
    return [sanitize_message_for_llm(message) for message in messages]


def sanitize_message_for_llm(message: Any) -> Any:
    if not isinstance(message, BaseMessage):
        return message

    content = message_content(message)
    if content == message.content:
        return message
    return message.model_copy(update={"content": content})
