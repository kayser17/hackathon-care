from __future__ import annotations

from statistics import mean

import torch

from .model_registry import get_toxicity_components
from .schemas import NormalizedMessage, ToxicityArtifacts


DEFAULT_TOXIC_THRESHOLD = 0.7


def score_toxicity(
    messages: list[NormalizedMessage],
    *,
    toxic_threshold: float = DEFAULT_TOXIC_THRESHOLD,
) -> ToxicityArtifacts:
    if not messages:
        return ToxicityArtifacts(
            per_message_scores=[],
            conversation_mean=0.0,
            conversation_max=0.0,
            toxic_message_ratio=0.0,
        )

    texts = [message.normalized_text for message in messages]
    tokenizer, model, device = get_toxicity_components()
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)
        probabilities = probs[:, 1].detach().cpu().tolist()

    scores = [float(score) for score in probabilities]
    toxic_ratio = sum(score >= toxic_threshold for score in scores) / len(scores)

    return ToxicityArtifacts(
        per_message_scores=scores,
        conversation_mean=round(mean(scores), 4),
        conversation_max=round(max(scores), 4),
        toxic_message_ratio=round(toxic_ratio, 4),
    )
