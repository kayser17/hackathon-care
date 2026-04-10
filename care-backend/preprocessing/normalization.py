from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import ConversationInput, NormalizedMessage, RawConversationMessage


WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_conversation(conversation: ConversationInput) -> list[NormalizedMessage]:
    sorted_messages = sorted(
        conversation.messages,
        key=lambda message: message.timestamp,
    )
    return [
        NormalizedMessage(
            index=index,
            speaker=message.speaker,
            timestamp=message.timestamp,
            original_text=message.text,
            normalized_text=normalize_text(message.text),
        )
        for index, message in enumerate(sorted_messages)
    ]


def load_conversation_json(path: str | Path) -> ConversationInput:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, list):
        raise ValueError("Conversation JSON must be a list of messages.")

    messages = [RawConversationMessage.model_validate(item) for item in payload]
    return ConversationInput(messages=messages)


def conversation_from_payload(payload: list[dict[str, Any]]) -> ConversationInput:
    messages = [RawConversationMessage.model_validate(item) for item in payload]
    return ConversationInput(messages=messages)
