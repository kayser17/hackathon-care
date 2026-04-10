from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RawConversationMessage(BaseModel):
    speaker: str = Field(min_length=1, max_length=120)
    timestamp: datetime
    text: str = Field(min_length=1, max_length=5000)


class ConversationInput(BaseModel):
    messages: list[RawConversationMessage] = Field(min_length=1)


@dataclass(slots=True)
class NormalizedMessage:
    index: int
    speaker: str
    timestamp: datetime
    original_text: str
    normalized_text: str


class EmotionMetrics(BaseModel):
    anger: float = Field(ge=0.0, le=1.0, default=0.0)
    sadness: float = Field(ge=0.0, le=1.0, default=0.0)
    fear: float = Field(ge=0.0, le=1.0, default=0.0)


class PreprocessingMetrics(BaseModel):
    toxicity: float = Field(ge=0.0, le=1.0)
    insult_score: float = Field(ge=0.0, le=1.0)
    emotion: EmotionMetrics = Field(default_factory=EmotionMetrics)
    manipulation_similarity: float = Field(ge=0.0, le=1.0, default=0.0)
    targeting_intensity: float = Field(ge=0.0, le=1.0, default=0.0)
    dominance_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    risk_trend: Literal["increasing", "stable", "decreasing"] = "stable"
    activity_anomaly: float = Field(ge=0.0, le=1.0, default=0.0)
    distress_signal: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


@dataclass(slots=True)
class ToxicityArtifacts:
    per_message_scores: list[float]
    conversation_mean: float
    conversation_max: float
    toxic_message_ratio: float
