from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MessageInput(BaseModel):
    author_id: str | None = Field(default=None, max_length=80)
    author_role: Literal["adolescent", "peer", "adult", "unknown"] = "unknown"
    content: str = Field(min_length=1, max_length=5000)
    created_at: datetime | None = None


class ConversationInput(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=120)
    subject_id: str | None = Field(default=None, max_length=120)
    messages: list[MessageInput] = Field(min_length=1)


class ExtractedSignal(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    count: int = Field(ge=0)
    trend: Literal["decreasing", "stable", "increasing"]
    rationale: str


class RedactedEvidence(BaseModel):
    signal_name: str
    message_index: int = Field(ge=0)
    snippet: str


class EscalationDecision(BaseModel):
    level: Literal["none", "monitor", "counselor_review", "urgent_review"]
    priority_score: float = Field(ge=0.0, le=1.0)
    rationale: str


class PreprocessingResult(BaseModel):
    focus_area: Literal["adolescent_mental_health_early_warning"] = (
        "adolescent_mental_health_early_warning"
    )
    risk_summary: str
    signals: list[ExtractedSignal]
    evidence: list[RedactedEvidence]
    escalation: EscalationDecision
    metadata: dict[str, int | float | str]
