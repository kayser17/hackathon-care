from __future__ import annotations

from collections import defaultdict

from .lexicons import (
    ANXIETY_PATTERNS,
    BULLYING_PATTERNS,
    DISTRESS_PATTERNS,
    HOPELESSNESS_PATTERNS,
    ISOLATION_PATTERNS,
    SELF_HARM_PATTERNS,
    TARGETING_PATTERNS,
    WITHDRAWAL_PATTERNS,
)
from .models import (
    ConversationInput,
    EscalationDecision,
    ExtractedSignal,
    PreprocessingResult,
    RedactedEvidence,
)
from .redaction import redact_text


SIGNAL_DEFINITIONS = {
    "emotional_distress": {
        "patterns": DISTRESS_PATTERNS,
        "rationale": "Captures direct expressions of emotional pain or inability to cope.",
    },
    "hopelessness": {
        "patterns": HOPELESSNESS_PATTERNS,
        "rationale": "Captures language suggesting futility, worthlessness, or loss of hope.",
    },
    "anxiety": {
        "patterns": ANXIETY_PATTERNS,
        "rationale": "Captures signs of acute anxiety, fear, or overwhelm.",
    },
    "social_isolation": {
        "patterns": ISOLATION_PATTERNS,
        "rationale": "Captures feelings of being alone, unsupported, or disconnected.",
    },
    "social_withdrawal": {
        "patterns": WITHDRAWAL_PATTERNS,
        "rationale": "Captures avoidance, disengagement, and reduced participation.",
    },
    "cyberbullying": {
        "patterns": BULLYING_PATTERNS + TARGETING_PATTERNS,
        "rationale": "Captures hostile or repeated targeting language consistent with cyberbullying.",
    },
    "self_harm_reference": {
        "patterns": SELF_HARM_PATTERNS,
        "rationale": "Captures explicit statements that may indicate elevated immediate risk.",
    },
}

SIGNAL_WEIGHTS = {
    "emotional_distress": 1.0,
    "hopelessness": 1.2,
    "anxiety": 0.8,
    "social_isolation": 1.0,
    "social_withdrawal": 1.0,
    "cyberbullying": 1.1,
    "self_harm_reference": 1.8,
}


def preprocess_conversation(conversation: ConversationInput) -> PreprocessingResult:
    lowered_messages = [message.content.lower() for message in conversation.messages]
    message_count = len(lowered_messages)
    half_index = max(1, message_count // 2)

    counts: dict[str, int] = defaultdict(int)
    first_half_counts: dict[str, int] = defaultdict(int)
    second_half_counts: dict[str, int] = defaultdict(int)
    evidence: list[RedactedEvidence] = []

    for index, message in enumerate(lowered_messages):
        for signal_name, definition in SIGNAL_DEFINITIONS.items():
            matched = [pattern for pattern in definition["patterns"] if pattern in message]
            if not matched:
                continue

            counts[signal_name] += len(matched)
            if index < half_index:
                first_half_counts[signal_name] += len(matched)
            else:
                second_half_counts[signal_name] += len(matched)

            if len(evidence) < 10:
                evidence.append(
                    RedactedEvidence(
                        signal_name=signal_name,
                        message_index=index,
                        snippet=redact_text(conversation.messages[index].content),
                    )
                )

    signals = [
        _build_signal(
            signal_name=signal_name,
            count=counts[signal_name],
            first_half_count=first_half_counts[signal_name],
            second_half_count=second_half_counts[signal_name],
            total_messages=message_count,
        )
        for signal_name in SIGNAL_DEFINITIONS
    ]

    priority_score = _calculate_priority_score(signals)
    escalation = _build_escalation(signals, priority_score)

    top_signals = [signal.name for signal in sorted(signals, key=lambda item: item.score, reverse=True) if signal.score > 0][:3]
    if top_signals:
        risk_summary = (
            "Preprocessing detected elevated signals in "
            + ", ".join(top_signals).replace("_", " ")
            + "."
        )
    else:
        risk_summary = "Preprocessing detected no elevated mental-health or cyberbullying signals."

    metadata = {
        "conversation_messages": message_count,
        "messages_with_evidence": len({item.message_index for item in evidence}),
        "priority_score": round(priority_score, 3),
        "detected_signal_count": sum(1 for signal in signals if signal.count > 0),
    }

    return PreprocessingResult(
        risk_summary=risk_summary,
        signals=signals,
        evidence=evidence,
        escalation=escalation,
        metadata=metadata,
    )


def _build_signal(
    signal_name: str,
    count: int,
    first_half_count: int,
    second_half_count: int,
    total_messages: int,
) -> ExtractedSignal:
    weighted_count = count * SIGNAL_WEIGHTS[signal_name]
    normalized = min(1.0, weighted_count / max(2, total_messages))
    trend = _trend_from_counts(first_half_count, second_half_count)

    return ExtractedSignal(
        name=signal_name,
        score=round(normalized, 3),
        count=count,
        trend=trend,
        rationale=SIGNAL_DEFINITIONS[signal_name]["rationale"],
    )


def _trend_from_counts(first_half_count: int, second_half_count: int) -> str:
    if second_half_count > first_half_count:
        return "increasing"
    if second_half_count < first_half_count:
        return "decreasing"
    return "stable"


def _calculate_priority_score(signals: list[ExtractedSignal]) -> float:
    score_by_name = {signal.name: signal.score for signal in signals}
    score = 0.0
    score += score_by_name["emotional_distress"] * 0.2
    score += score_by_name["hopelessness"] * 0.2
    score += score_by_name["anxiety"] * 0.1
    score += score_by_name["social_isolation"] * 0.15
    score += score_by_name["social_withdrawal"] * 0.1
    score += score_by_name["cyberbullying"] * 0.1
    score += score_by_name["self_harm_reference"] * 0.15

    increasing_signals = sum(1 for signal in signals if signal.trend == "increasing" and signal.score > 0)
    score += min(0.1, increasing_signals * 0.03)
    return round(min(score, 1.0), 3)


def _build_escalation(
    signals: list[ExtractedSignal],
    priority_score: float,
) -> EscalationDecision:
    score_by_name = {signal.name: signal.score for signal in signals}
    if score_by_name["self_harm_reference"] >= 0.3 or priority_score >= 0.7:
        return EscalationDecision(
            level="urgent_review",
            priority_score=priority_score,
            rationale=(
                "High-priority review recommended because explicit self-harm language "
                "or a dense combination of distress signals was detected."
            ),
        )

    if (
        priority_score >= 0.45
        or score_by_name["hopelessness"] >= 0.3
        or score_by_name["cyberbullying"] >= 0.35
    ):
        return EscalationDecision(
            level="counselor_review",
            priority_score=priority_score,
            rationale=(
                "Counselor review recommended because the conversation contains "
                "meaningful signs of distress, social risk, or targeted harm."
            ),
        )

    if priority_score >= 0.2:
        return EscalationDecision(
            level="monitor",
            priority_score=priority_score,
            rationale="Monitoring recommended because weak but non-zero risk signals were detected.",
        )

    return EscalationDecision(
        level="none",
        priority_score=priority_score,
        rationale="No escalation recommended because preprocessing found no meaningful risk pattern.",
    )
