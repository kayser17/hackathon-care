from __future__ import annotations

from statistics import mean

from .emotions_model import predict_emotion_scores_batch
from .schemas import EmotionMetrics, NormalizedMessage


TARGET_EMOTIONS = ("anger", "sadness", "fear")


def score_emotions(messages: list[NormalizedMessage]) -> EmotionMetrics:
    if not messages:
        return EmotionMetrics()

    scores_by_emotion: dict[str, list[float]] = {emotion: [] for emotion in TARGET_EMOTIONS}
    predicted_scores_batch = predict_emotion_scores_batch(
        [message.normalized_text for message in messages]
    )

    for predicted_scores in predicted_scores_batch:
        for emotion in TARGET_EMOTIONS:
            scores_by_emotion[emotion].append(float(predicted_scores.get(emotion, 0.0)))

    return EmotionMetrics(
        anger=round(mean(scores_by_emotion["anger"]) if scores_by_emotion["anger"] else 0.0, 4),
        sadness=round(mean(scores_by_emotion["sadness"]) if scores_by_emotion["sadness"] else 0.0, 4),
        fear=round(mean(scores_by_emotion["fear"]) if scores_by_emotion["fear"] else 0.0, 4),
    )
