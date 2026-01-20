"""Prompt construction and response helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from .storage import MessageRecord


SYSTEM_PROMPT = (
    "Reply briefly in 10 words or less."
)


class MessageLike(Protocol):
    text: str
    sender_id: str
    sender_short_name: Optional[str]
    sender_long_name: Optional[str]
    channel: Optional[int]
    is_dm: bool


@dataclass
class PromptParts:
    system: str
    user: str


def strip_trigger_prefix(text: str, prefix: str) -> str:
    if prefix and text.startswith(prefix):
        return text[len(prefix) :].lstrip()
    return text


def build_prompt(
    message: MessageLike,
    history: Iterable[MessageRecord],
    max_reply_chars: int,
) -> PromptParts:
    sender_name = message.sender_short_name or message.sender_long_name or "Unknown"
    sender_long = message.sender_long_name or ""
    if message.is_dm:
        channel_label = "DM"
    else:
        channel_label = str(message.channel) if message.channel is not None else "unknown"

    header_lines = [
        f"Sender: {sender_name}",
        f"Sender ID: {message.sender_id}",
        f"Channel: {channel_label}",
    ]
    if sender_long and sender_long != sender_name:
        header_lines.insert(1, f"Sender Long Name: {sender_long}")

    history_lines = []
    for item in history:
        role = "User" if item.direction == "in" else "Assistant"
        history_lines.append(f"{role}: {item.text}")

    history_block = "\n".join(history_lines) if history_lines else "(none)"

    user_prompt = "\n".join(
        [
            *header_lines,
            "Message:",
            message.text,
            "",
            "Conversation history:",
            history_block,
            "",
            f"Reply in <= {max_reply_chars} characters.",
        ]
    )

    return PromptParts(system=SYSTEM_PROMPT, user=user_prompt)


def normalize_reply(text: str) -> str:
    return " ".join(text.strip().split())


def enforce_max_length(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def chunk_text(text: str, chunk_size: int) -> list[str]:
    if chunk_size <= 0:
        return [text]
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
