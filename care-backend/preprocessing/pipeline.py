from __future__ import annotations

from .distress import compute_distress_signal
from .emotion import score_emotions
from .insults import compute_insult_score
from .manipulation import compute_manipulation_similarity
from .normalization import load_conversation_json, normalize_conversation
from .schemas import ConversationInput, PreprocessingMetrics
from .toxicity import score_toxicity


def preprocess_conversation(conversation: ConversationInput) -> PreprocessingMetrics:
    normalized_messages = normalize_conversation(conversation)
    toxicity_artifacts = score_toxicity(normalized_messages)
    insult_score = compute_insult_score(toxicity_artifacts)
    emotion = score_emotions(normalized_messages)
    manipulation_similarity = compute_manipulation_similarity(normalized_messages)
    distress_signal = compute_distress_signal(normalized_messages)
    confidence = _compute_confidence(
        toxicity=toxicity_artifacts.conversation_mean,
        insult_score=insult_score,
        toxic_ratio=toxicity_artifacts.toxic_message_ratio,
        message_count=len(normalized_messages),
        manipulation_similarity=manipulation_similarity,
        distress_signal=distress_signal,
        emotion_strength=max(emotion.anger, emotion.sadness, emotion.fear),
    )

    return PreprocessingMetrics(
        toxicity=toxicity_artifacts.conversation_mean,
        insult_score=insult_score,
        emotion=emotion,
        manipulation_similarity=manipulation_similarity,
        targeting_intensity=0.0,
        dominance_ratio=0.0,
        risk_trend="stable",
        activity_anomaly=0.0,
        distress_signal=distress_signal,
        confidence=confidence,
    )


def preprocess_conversation_file(path: str) -> PreprocessingMetrics:
    conversation = load_conversation_json(path)
    return preprocess_conversation(conversation)


def _compute_confidence(
    *,
    toxicity: float,
    insult_score: float,
    toxic_ratio: float,
    message_count: int,
    manipulation_similarity: float,
    distress_signal: float,
    emotion_strength: float,
) -> float:
    confidence = 0.25
    confidence += min(0.25, toxicity * 0.25)
    confidence += min(0.2, insult_score * 0.25)
    confidence += min(0.15, toxic_ratio * 0.15)
    confidence += 0.15 if message_count >= 10 else 0.05
    confidence += min(0.1, manipulation_similarity * 0.1)
    confidence += min(0.1, distress_signal * 0.1)
    confidence += min(0.05, emotion_strength * 0.05)

    if toxicity > 0.6 and insult_score > 0.5:
        confidence += 0.1
    if distress_signal > 0.6 and emotion_strength > 0.3:
        confidence += 0.05

    return round(min(confidence, 1.0), 4)
