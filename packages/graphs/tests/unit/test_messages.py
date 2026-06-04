from langchain_core.messages import AIMessage, HumanMessage
from rag_graphs.util.messages import message_content, sanitize_messages_for_llm


def test_message_content_uses_visible_text_blocks_only():
    message = AIMessage(
        content=[
            {"type": "thinking", "thinking": "hidden chain of thought"},
            {"type": "text", "text": "Visible"},
            {"type": "reasoning", "reasoning": "hidden reasoning"},
            {"type": "text", "text": " answer"},
        ]
    )

    assert message_content(message) == "Visible answer"


def test_message_content_does_not_stringify_unknown_objects():
    message = AIMessage(content=[{"type": "thinking", "thinking": "hidden"}, {"type": "unknown", "value": 123}])

    assert message_content(message) == ""


def test_sanitize_messages_for_llm_strips_hidden_blocks_without_mutating_original():
    assistant_message = AIMessage(
        content=[
            {"type": "thinking", "thinking": "hidden chain of thought"},
            {"type": "text", "text": "Visible answer"},
        ]
    )

    sanitized = sanitize_messages_for_llm([HumanMessage(content="Hello"), assistant_message])

    assert sanitized[0].content == "Hello"
    assert sanitized[1].content == "Visible answer"
    assert assistant_message.content == [
        {"type": "thinking", "thinking": "hidden chain of thought"},
        {"type": "text", "text": "Visible answer"},
    ]
