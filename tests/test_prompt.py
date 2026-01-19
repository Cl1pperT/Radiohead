from dataclasses import dataclass

from meshtastic_llm_bridge.prompt import build_prompt
from meshtastic_llm_bridge.storage import MessageRecord


@dataclass
class DummyMessage:
    text: str
    sender_id: str
    sender_short_name: str | None
    sender_long_name: str | None
    channel: int | None
    is_dm: bool


def test_build_prompt_includes_history_and_limits() -> None:
    message = DummyMessage(
        text="hello there",
        sender_id="!abcd1234",
        sender_short_name="AL",
        sender_long_name="Alice",
        channel=1,
        is_dm=False,
    )
    history = [
        MessageRecord(
            direction="in",
            sender_id="!abcd1234",
            sender_short_name="AL",
            sender_long_name="Alice",
            channel=1,
            text="hi",
            timestamp=0.0,
            latency_ms=None,
            message_id=None,
        ),
        MessageRecord(
            direction="out",
            sender_id="!abcd1234",
            sender_short_name="AL",
            sender_long_name="Alice",
            channel=1,
            text="hello back",
            timestamp=1.0,
            latency_ms=None,
            message_id=None,
        ),
    ]

    prompt = build_prompt(message=message, history=history, max_reply_chars=120)

    assert "Sender: AL" in prompt.user
    assert "Sender ID: !abcd1234" in prompt.user
    assert "Conversation history:" in prompt.user
    assert "User: hi" in prompt.user
    assert "Assistant: hello back" in prompt.user
    assert "Reply in <= 120 characters." in prompt.user
