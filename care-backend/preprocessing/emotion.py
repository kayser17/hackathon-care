from __future__ import annotations

from statistics import mean

import torch

from .model_registry import get_emotion_components
from .schemas import EmotionMetrics, NormalizedMessage


TARGET_EMOTIONS = ("anger", "sadness", "fear")


def score_emotions(messages: list[NormalizedMessage]) -> EmotionMetrics:
    if not messages:
        return EmotionMetrics()

    texts = [message.normalized_text for message in messages]
    tokenizer, model, device = get_emotion_components()
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    ).to(device)

    with torch.no_grad():
        logits = model(**inputs).logits
        probabilities = torch.softmax(logits, dim=-1).detach().cpu()

    id2label = {int(key): value.lower() for key, value in model.config.id2label.items()}
    scores_by_emotion: dict[str, list[float]] = {emotion: [] for emotion in TARGET_EMOTIONS}

    for row in probabilities.tolist():
        for index, value in enumerate(row):
            label = id2label.get(index)
            if label in scores_by_emotion:
                scores_by_emotion[label].append(float(value))

    return EmotionMetrics(
        anger=round(mean(scores_by_emotion["anger"]) if scores_by_emotion["anger"] else 0.0, 4),
        sadness=round(mean(scores_by_emotion["sadness"]) if scores_by_emotion["sadness"] else 0.0, 4),
        fear=round(mean(scores_by_emotion["fear"]) if scores_by_emotion["fear"] else 0.0, 4),
    )
