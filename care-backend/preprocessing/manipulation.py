from __future__ import annotations

from .model_registry import get_similarity_model
from .resources import load_manipulation_patterns
from .schemas import NormalizedMessage


def compute_manipulation_similarity(messages: list[NormalizedMessage]) -> float:
    if not messages:
        return 0.0

    patterns = load_manipulation_patterns()
    model = get_similarity_model()
    message_embeddings = model.encode(
        [message.normalized_text for message in messages],
        normalize_embeddings=True,
        convert_to_tensor=True,
    )
    pattern_embeddings = model.encode(
        patterns,
        normalize_embeddings=True,
        convert_to_tensor=True,
    )
    similarities = model.similarity(message_embeddings, pattern_embeddings)
    return round(max(0.0, min(1.0, float(similarities.max().item()))), 4)
