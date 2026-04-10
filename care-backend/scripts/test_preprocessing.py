from __future__ import annotations

import json
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from preprocessing import ConversationInput, MessageInput, preprocess_conversation


SAMPLE_CONVERSATIONS = {
    "baseline": ConversationInput(
        conversation_id="baseline",
        subject_id="subject-001",
        messages=[
            MessageInput(
                author_role="peer",
                content="Are you joining the group study later?",
            ),
            MessageInput(
                author_role="adolescent",
                content="Maybe. I am just tired after school.",
            ),
            MessageInput(
                author_role="peer",
                content="No problem, let us know if you want the notes.",
            ),
        ],
    ),
    "distress": ConversationInput(
        conversation_id="distress",
        subject_id="subject-002",
        messages=[
            MessageInput(
                author_role="adolescent",
                content="I feel empty lately and I do not talk to anyone anymore.",
            ),
            MessageInput(
                author_role="peer",
                content="You have seemed distant all week. Are you okay?",
            ),
            MessageInput(
                author_role="adolescent",
                content="Honestly, what is the point. Nothing feels better.",
            ),
        ],
    ),
    "bullying": ConversationInput(
        conversation_id="bullying",
        subject_id="subject-003",
        messages=[
            MessageInput(
                author_role="peer",
                content="Everyone hates you. We are all laughing at you in the group chat.",
            ),
            MessageInput(
                author_role="adolescent",
                content="They keep posting about me and they will not stop.",
            ),
            MessageInput(
                author_role="adolescent",
                content="I skipped school today because I cannot deal with this anymore.",
            ),
        ],
    ),
    "urgent": ConversationInput(
        conversation_id="urgent",
        subject_id="subject-004",
        messages=[
            MessageInput(
                author_role="adolescent",
                content="I feel trapped and nobody would notice if I disappeared.",
            ),
            MessageInput(
                author_role="peer",
                content="Please answer me. I am worried about you.",
            ),
            MessageInput(
                author_role="adolescent",
                content="I do not want to be here anymore. I want to disappear.",
            ),
        ],
    ),
}


def main() -> int:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "distress"
    if scenario not in SAMPLE_CONVERSATIONS:
        available = ", ".join(sorted(SAMPLE_CONVERSATIONS))
        print(f"Unknown scenario '{scenario}'. Available: {available}", file=sys.stderr)
        return 1

    result = preprocess_conversation(SAMPLE_CONVERSATIONS[scenario])
    print(json.dumps(result.model_dump(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
