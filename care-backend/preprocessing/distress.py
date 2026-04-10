from __future__ import annotations

from .model_registry import get_similarity_model
from .resources import load_distress_patterns
from .schemas import NormalizedMessage


def compute_distress_signal(messages: list[NormalizedMessage], *, top_k: int = 3) -> float:
    if not messages:
        return 0.0

    patterns = load_distress_patterns()
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
    similarities = model.similarity(message_embeddings, pattern_embeddings).flatten()
    values = [float(value) for value in similarities.tolist()]
    if not values:
        return 0.0

    k = min(top_k, len(values))
    top_values = sorted(values, reverse=True)[:k]
    return round(max(0.0, min(1.0, sum(top_values) / len(top_values))), 4)
