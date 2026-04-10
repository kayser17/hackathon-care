from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from PostProceso import (
    EmotionMetrics,
    HistoricalChunkMetrics,
    LLMResult,
    PostprocessDecision,
    PreprocessingMetrics,
    compute_current_intensity,
    compute_final_type_scores,
    compute_historical_escalation,
    compute_llm_support_score,
    compute_llm_type_scores,
    compute_trend_type_score,
    compute_type_scores,
    normalize_llm_risk_type,
    process_llm_true_result,
    should_create_new_alert,
    should_escalate_existing_alert,
)


def build_llm_result(
    *,
    cyberbullying: float = 0.0,
    grooming: float = 0.0,
    self_harm: float = 0.0,
    severity: str = "medium",
    confidence: float = 0.8,
    key_evidence: list[str] | None = None,
    reasoning: str = "Synthetic test reasoning",
    conversation_summary: str = "Synthetic test summary",
) -> LLMResult:
    return LLMResult(
        risk_detected=True,
        risk_types={
            "cyberbullying": cyberbullying,
            "grooming": grooming,
            "self_harm": self_harm,
        },
        severity=severity,
        confidence=confidence,
        key_evidence=key_evidence or ["synthetic evidence"],
        reasoning=reasoning,
        conversation_summary=conversation_summary,
    )


def build_metrics(
    *,
    toxicity: float = 0.0,
    insult_score: float = 0.0,
    anger: float = 0.0,
    sadness: float = 0.0,
    fear: float = 0.0,
    manipulation_similarity: float = 0.0,
    targeting_intensity: float = 0.0,
    dominance_ratio: float = 0.0,
    risk_trend: str = "stable",
    activity_anomaly: float = 0.0,
    distress_signal: float = 0.0,
    confidence: float = 0.8,
) -> PreprocessingMetrics:
    return PreprocessingMetrics(
        toxicity=toxicity,
        insult_score=insult_score,
        emotion=EmotionMetrics(anger=anger, sadness=sadness, fear=fear),
        manipulation_similarity=manipulation_similarity,
        targeting_intensity=targeting_intensity,
        dominance_ratio=dominance_ratio,
        risk_trend=risk_trend,
        activity_anomaly=activity_anomaly,
        distress_signal=distress_signal,
        confidence=confidence,
    )


def build_historical(
    conversation_id: str,
    snapshots: list[dict[str, float]],
    *,
    base_time: datetime | None = None,
) -> list[HistoricalChunkMetrics]:
    base_time = base_time or datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    items: list[HistoricalChunkMetrics] = []
    for idx, values in enumerate(snapshots):
        items.append(
            HistoricalChunkMetrics(
                chunk_id=f"chunk-{idx + 1}",
                conversation_id=conversation_id,
                created_at=base_time + timedelta(minutes=idx * 15),
                toxicity=values.get("toxicity", 0.0),
                insult_score=values.get("insult_score", 0.0),
                manipulation_similarity=values.get("manipulation_similarity", 0.0),
                targeting_intensity=values.get("targeting_intensity", 0.0),
                dominance_ratio=values.get("dominance_ratio", 0.0),
                activity_anomaly=values.get("activity_anomaly", 0.0),
                distress_signal=values.get("distress_signal", 0.0),
                confidence=values.get("confidence", 0.7),
                risk_trend=values.get("risk_trend", "stable"),
                emotion_anger=values.get("anger", 0.0),
                emotion_sadness=values.get("sadness", 0.0),
                emotion_fear=values.get("fear", 0.0),
            )
        )
    return items


def run_case(
    *,
    name: str,
    child_user_id: str,
    conversation_id: str,
    chunk_id: str,
    llm_result: LLMResult,
    current_metrics: PreprocessingMetrics,
    historical_metrics: list[HistoricalChunkMetrics],
    existing_open_alerts: list[dict] | None = None,
) -> PostprocessDecision:
    decision = process_llm_true_result(
        child_user_id=child_user_id,
        conversation_id=conversation_id,
        chunk_id=chunk_id,
        llm_result=llm_result,
        current_metrics=current_metrics,
        historical_metrics=historical_metrics,
        existing_open_alerts=existing_open_alerts,
    )
    print(f"{name}:")
    print(decision)
    return decision


def test_normalize_llm_risk_type():
    assert normalize_llm_risk_type(build_llm_result(cyberbullying=0.9)) == "bullying"
    assert normalize_llm_risk_type(build_llm_result(grooming=0.9)) == "grooming"
    assert normalize_llm_risk_type(build_llm_result(self_harm=0.9)) == "distress"


def test_bullying_intensity_high():
    metrics = build_metrics(
        toxicity=0.9,
        insult_score=0.9,
        anger=0.8,
        targeting_intensity=0.92,
        dominance_ratio=0.88,
        distress_signal=0.6,
        activity_anomaly=0.5,
        risk_trend="increasing",
    )
    score = compute_current_intensity("bullying", metrics)
    print("bullying_intensity_high:", score)
    assert score >= 0.8


def test_grooming_intensity_high():
    metrics = build_metrics(
        manipulation_similarity=0.94,
        targeting_intensity=0.85,
        dominance_ratio=0.9,
        fear=0.7,
        distress_signal=0.66,
        activity_anomaly=0.7,
        confidence=0.9,
        risk_trend="increasing",
    )
    score = compute_current_intensity("grooming", metrics)
    print("grooming_intensity_high:", score)
    assert score >= 0.85


def test_distress_intensity_moderate():
    metrics = build_metrics(
        sadness=0.75,
        fear=0.58,
        distress_signal=0.7,
        activity_anomaly=0.45,
        anger=0.2,
        risk_trend="stable",
    )
    score = compute_current_intensity("distress", metrics)
    print("distress_intensity_moderate:", score)
    assert 0.45 <= score <= 0.75


def test_metric_type_selection_prefers_bullying():
    metrics = build_metrics(toxicity=0.86, insult_score=0.9, targeting_intensity=0.88, dominance_ratio=0.84, anger=0.68)
    type_scores = compute_type_scores(metrics)
    risk_type = max(type_scores, key=type_scores.get)
    print("metric_type_selection:", risk_type, type_scores)
    assert type_scores["bullying"] > type_scores["grooming"]


def test_llm_support_bullying_high():
    llm = build_llm_result(cyberbullying=0.93, severity="high", confidence=0.89, key_evidence=["a", "b"])
    support = compute_llm_support_score("bullying", llm)
    print("llm_support_bullying_high:", support)
    assert support >= 0.85


def test_llm_support_distress_medium():
    llm = build_llm_result(self_harm=0.8, severity="medium", confidence=0.78)
    support = compute_llm_support_score("distress", llm)
    print("llm_support_distress_medium:", support)
    assert support >= 0.65


def test_llm_disagreement_can_still_favor_llm_when_metrics_are_not_decisive():
    metrics = build_metrics(
        toxicity=0.93,
        insult_score=0.92,
        targeting_intensity=0.9,
        dominance_ratio=0.84,
        anger=0.8,
        manipulation_similarity=0.08,
        fear=0.12,
        distress_signal=0.18,
        activity_anomaly=0.32,
        confidence=0.86,
        risk_trend="increasing",
    )
    llm = build_llm_result(grooming=0.95, cyberbullying=0.03, severity="high", confidence=0.92)
    decision = process_llm_true_result(
        child_user_id="child-disagree",
        conversation_id="conv-disagree",
        chunk_id="chunk-disagree",
        llm_result=llm,
        current_metrics=metrics,
        historical_metrics=build_historical(
            "conv-disagree",
            [
                {"toxicity": 0.68, "insult_score": 0.7, "targeting_intensity": 0.66, "dominance_ratio": 0.6, "anger": 0.56},
                {"toxicity": 0.77, "insult_score": 0.79, "targeting_intensity": 0.75, "dominance_ratio": 0.69, "anger": 0.63, "risk_trend": "increasing"},
            ],
        ),
    )
    print("llm_disagreement:", decision)
    assert decision.risk_type == "grooming"


def test_llm_can_push_close_call_to_grooming():
    metrics = build_metrics(
        toxicity=0.42,
        insult_score=0.36,
        manipulation_similarity=0.66,
        targeting_intensity=0.56,
        dominance_ratio=0.61,
        fear=0.48,
        distress_signal=0.36,
        confidence=0.82,
    )
    llm = build_llm_result(grooming=0.96, cyberbullying=0.08, self_harm=0.04, severity="high", confidence=0.94)
    decision = process_llm_true_result(
        child_user_id="child-close-grooming",
        conversation_id="conv-close-grooming",
        chunk_id="chunk-close-grooming",
        llm_result=llm,
        current_metrics=metrics,
        historical_metrics=[],
    )
    print("llm_push_close_call:", decision)
    assert decision.risk_type == "grooming"


def test_trend_score_rewards_rising_bullying():
    current = build_metrics(
        toxicity=0.78,
        insult_score=0.8,
        targeting_intensity=0.79,
        dominance_ratio=0.7,
        anger=0.69,
        risk_trend="increasing",
    )
    history = build_historical(
        "conv-trend-bullying",
        [
            {"toxicity": 0.42, "insult_score": 0.45, "targeting_intensity": 0.43, "dominance_ratio": 0.4, "anger": 0.38},
            {"toxicity": 0.56, "insult_score": 0.58, "targeting_intensity": 0.57, "dominance_ratio": 0.52, "anger": 0.49, "risk_trend": "increasing"},
            {"toxicity": 0.68, "insult_score": 0.72, "targeting_intensity": 0.71, "dominance_ratio": 0.62, "anger": 0.58, "risk_trend": "increasing"},
        ],
    )
    trend_score, historical = compute_trend_type_score("bullying", current, history)
    print("trend_score_bullying:", trend_score, historical)
    assert trend_score >= 0.45


def test_final_type_score_combines_metrics_llm_and_trend():
    metric_scores = {"bullying": 0.72, "grooming": 0.4, "distress": 0.22}
    llm_scores = {"bullying": 0.78, "grooming": 0.12, "distress": 0.1}
    trend_scores = {"bullying": 0.64, "grooming": 0.2, "distress": 0.18}
    final_scores = compute_final_type_scores(metric_scores, llm_scores, trend_scores)
    print("final_type_scores:", final_scores)
    assert final_scores["bullying"] > final_scores["grooming"]
    assert final_scores["bullying"] > final_scores["distress"]


def test_decreasing_trend_cools_down_distress_severity():
    high_history = build_historical(
        "conv-recovering",
        [
            {"distress_signal": 0.84, "sadness": 0.82, "fear": 0.7, "activity_anomaly": 0.66},
            {"distress_signal": 0.76, "sadness": 0.74, "fear": 0.64, "activity_anomaly": 0.55, "risk_trend": "decreasing"},
            {"distress_signal": 0.64, "sadness": 0.68, "fear": 0.55, "activity_anomaly": 0.48, "risk_trend": "decreasing"},
        ],
    )
    decision = process_llm_true_result(
        child_user_id="child-recovering",
        conversation_id="conv-recovering",
        chunk_id="chunk-recovering",
        llm_result=build_llm_result(self_harm=0.72, severity="medium", confidence=0.8),
        current_metrics=build_metrics(
            sadness=0.56,
            fear=0.43,
            distress_signal=0.49,
            activity_anomaly=0.36,
            risk_trend="decreasing",
            confidence=0.82,
        ),
        historical_metrics=high_history,
    )
    print("decreasing_distress:", decision)
    assert decision.risk_type == "distress"
    assert decision.postprocess_decision == "follow_up"


def test_metrics_override_moderate_llm_when_bullying_is_clear():
    decision = process_llm_true_result(
        child_user_id="child-override",
        conversation_id="conv-override",
        chunk_id="chunk-override",
        llm_result=build_llm_result(grooming=0.62, cyberbullying=0.22, severity="medium", confidence=0.74),
        current_metrics=build_metrics(
            toxicity=0.92,
            insult_score=0.9,
            targeting_intensity=0.89,
            dominance_ratio=0.84,
            anger=0.8,
            manipulation_similarity=0.14,
            fear=0.2,
            confidence=0.86,
            risk_trend="increasing",
        ),
        historical_metrics=build_historical(
            "conv-override",
            [
                {"toxicity": 0.72, "insult_score": 0.7, "targeting_intensity": 0.68, "dominance_ratio": 0.62, "anger": 0.6},
                {"toxicity": 0.79, "insult_score": 0.77, "targeting_intensity": 0.75, "dominance_ratio": 0.68, "anger": 0.66, "risk_trend": "increasing"},
            ],
        ),
    )
    print("metrics_override_llm:", decision)
    assert decision.risk_type == "bullying"


def test_low_metrics_and_low_llm_stay_discarded():
    decision = process_llm_true_result(
        child_user_id="child-low",
        conversation_id="conv-low",
        chunk_id="chunk-low",
        llm_result=build_llm_result(cyberbullying=0.18, grooming=0.21, self_harm=0.16, severity="low", confidence=0.42),
        current_metrics=build_metrics(
            toxicity=0.12,
            insult_score=0.1,
            targeting_intensity=0.11,
            dominance_ratio=0.08,
            manipulation_similarity=0.09,
            sadness=0.12,
            fear=0.08,
            distress_signal=0.1,
            confidence=0.5,
        ),
        historical_metrics=[],
    )
    print("low_low_discarded:", decision)
    assert decision.validated_risk is False


def test_follow_up_boundary_stays_below_guardian():
    decision = process_llm_true_result(
        child_user_id="child-boundary-follow",
        conversation_id="conv-boundary-follow",
        chunk_id="chunk-boundary-follow",
        llm_result=build_llm_result(cyberbullying=0.66, severity="medium", confidence=0.78),
        current_metrics=build_metrics(
            toxicity=0.63,
            insult_score=0.62,
            targeting_intensity=0.61,
            dominance_ratio=0.52,
            anger=0.48,
            confidence=0.79,
            risk_trend="stable",
        ),
        historical_metrics=build_historical(
            "conv-boundary-follow",
            [
                {"toxicity": 0.44, "insult_score": 0.43, "targeting_intensity": 0.4, "dominance_ratio": 0.36},
                {"toxicity": 0.5, "insult_score": 0.48, "targeting_intensity": 0.45, "dominance_ratio": 0.4},
            ],
        ),
    )
    print("follow_up_boundary:", decision)
    assert 45 <= decision.severity_score < 70
    assert decision.postprocess_decision == "follow_up"


def test_notify_guardian_boundary_crosses_70():
    decision = process_llm_true_result(
        child_user_id="child-boundary-guardian",
        conversation_id="conv-boundary-guardian",
        chunk_id="chunk-boundary-guardian",
        llm_result=build_llm_result(cyberbullying=0.84, severity="high", confidence=0.87),
        current_metrics=build_metrics(
            toxicity=0.76,
            insult_score=0.79,
            targeting_intensity=0.8,
            dominance_ratio=0.67,
            anger=0.64,
            confidence=0.83,
            risk_trend="increasing",
        ),
        historical_metrics=build_historical(
            "conv-boundary-guardian",
            [
                {"toxicity": 0.52, "insult_score": 0.54, "targeting_intensity": 0.48, "dominance_ratio": 0.42},
                {"toxicity": 0.63, "insult_score": 0.66, "targeting_intensity": 0.61, "dominance_ratio": 0.54, "risk_trend": "increasing"},
                {"toxicity": 0.7, "insult_score": 0.72, "targeting_intensity": 0.71, "dominance_ratio": 0.61, "risk_trend": "increasing"},
            ],
        ),
    )
    print("notify_guardian_boundary:", decision)
    assert decision.severity_score >= 70
    assert decision.postprocess_decision == "notify_guardian"


def test_distress_llm_can_win_when_metrics_are_close():
    decision = process_llm_true_result(
        child_user_id="child-close-distress",
        conversation_id="conv-close-distress",
        chunk_id="chunk-close-distress",
        llm_result=build_llm_result(self_harm=0.93, cyberbullying=0.18, severity="high", confidence=0.91),
        current_metrics=build_metrics(
            toxicity=0.34,
            insult_score=0.28,
            sadness=0.52,
            fear=0.49,
            distress_signal=0.51,
            activity_anomaly=0.39,
            anger=0.22,
            confidence=0.8,
            risk_trend="stable",
        ),
        historical_metrics=build_historical(
            "conv-close-distress",
            [
                {"distress_signal": 0.28, "sadness": 0.3, "fear": 0.26, "activity_anomaly": 0.21},
                {"distress_signal": 0.33, "sadness": 0.36, "fear": 0.29, "activity_anomaly": 0.24},
            ],
        ),
    )
    print("close_distress_llm_wins:", decision)
    assert decision.risk_type == "distress"


def test_grooming_decreasing_trend_reduces_but_keeps_type():
    decision = process_llm_true_result(
        child_user_id="child-grooming-down",
        conversation_id="conv-grooming-down",
        chunk_id="chunk-grooming-down",
        llm_result=build_llm_result(grooming=0.86, severity="medium", confidence=0.84),
        current_metrics=build_metrics(
            manipulation_similarity=0.7,
            targeting_intensity=0.68,
            dominance_ratio=0.64,
            fear=0.46,
            distress_signal=0.38,
            activity_anomaly=0.4,
            confidence=0.82,
            risk_trend="decreasing",
        ),
        historical_metrics=build_historical(
            "conv-grooming-down",
            [
                {"manipulation_similarity": 0.82, "targeting_intensity": 0.78, "dominance_ratio": 0.7, "fear": 0.58},
                {"manipulation_similarity": 0.78, "targeting_intensity": 0.74, "dominance_ratio": 0.67, "fear": 0.53, "risk_trend": "decreasing"},
                {"manipulation_similarity": 0.73, "targeting_intensity": 0.7, "dominance_ratio": 0.65, "fear": 0.49, "risk_trend": "decreasing"},
            ],
        ),
    )
    print("grooming_decreasing:", decision)
    assert decision.risk_type == "grooming"
    assert decision.severity_score < 80


def test_bullying_open_alert_not_escalated_when_same_band():
    decision = process_llm_true_result(
        child_user_id="child-bullying-existing",
        conversation_id="conv-bullying-existing",
        chunk_id="chunk-bullying-existing",
        llm_result=build_llm_result(cyberbullying=0.83, severity="high", confidence=0.85),
        current_metrics=build_metrics(
            toxicity=0.75,
            insult_score=0.78,
            targeting_intensity=0.77,
            dominance_ratio=0.65,
            anger=0.6,
            confidence=0.82,
            risk_trend="increasing",
        ),
        historical_metrics=build_historical(
            "conv-bullying-existing",
            [
                {"toxicity": 0.56, "insult_score": 0.58, "targeting_intensity": 0.53, "dominance_ratio": 0.48},
                {"toxicity": 0.65, "insult_score": 0.68, "targeting_intensity": 0.64, "dominance_ratio": 0.55, "risk_trend": "increasing"},
            ],
        ),
        existing_open_alerts=[
            {
                "id": "alert-bull-1",
                "alert_type": "bullying",
                "alert_level": "high",
                "status": "open",
                "updated_at": "2026-04-10T08:00:00+00:00",
                "created_at": "2026-04-10T07:00:00+00:00",
            }
        ],
    )
    print("bullying_existing_same_band:", decision)
    assert decision.update_existing_alert is False


def test_historical_escalation_chronic_high():
    historical = build_historical(
        "conv-chronic",
        [
            {"toxicity": 0.86, "insult_score": 0.88, "targeting_intensity": 0.87, "dominance_ratio": 0.84, "anger": 0.8, "risk_trend": "increasing"},
            {"toxicity": 0.88, "insult_score": 0.9, "targeting_intensity": 0.89, "dominance_ratio": 0.86, "anger": 0.82, "risk_trend": "increasing"},
            {"toxicity": 0.9, "insult_score": 0.91, "targeting_intensity": 0.9, "dominance_ratio": 0.88, "anger": 0.84, "risk_trend": "increasing"},
            {"toxicity": 0.91, "insult_score": 0.92, "targeting_intensity": 0.92, "dominance_ratio": 0.89, "anger": 0.85, "risk_trend": "increasing"},
            {"toxicity": 0.92, "insult_score": 0.93, "targeting_intensity": 0.93, "dominance_ratio": 0.9, "anger": 0.86, "risk_trend": "increasing"},
        ],
    )
    current = build_metrics(
        toxicity=0.94,
        insult_score=0.95,
        targeting_intensity=0.95,
        dominance_ratio=0.91,
        anger=0.88,
        risk_trend="increasing",
    )
    result = compute_historical_escalation("bullying", current, historical)
    print("historical_escalation_chronic_high:", result)
    assert result["trend_status"] in {"chronic_high", "sustained_increase"}
    assert result["historical_escalation_score"] >= 0.6


def test_bullying_sustained_follow_up_or_guardian():
    decision = run_case(
        name="bullying_sustained",
        child_user_id="child-1",
        conversation_id="conv-bullying",
        chunk_id="current-bullying",
        llm_result=build_llm_result(
            cyberbullying=0.91,
            grooming=0.04,
            self_harm=0.05,
            severity="high",
            confidence=0.89,
            key_evidence=["insults repeated", "targeted hostility"],
        ),
        current_metrics=build_metrics(
            toxicity=0.82,
            insult_score=0.87,
            anger=0.76,
            sadness=0.31,
            fear=0.18,
            manipulation_similarity=0.22,
            targeting_intensity=0.86,
            dominance_ratio=0.81,
            risk_trend="increasing",
            activity_anomaly=0.57,
            distress_signal=0.62,
            confidence=0.84,
        ),
        historical_metrics=build_historical(
            "conv-bullying",
            [
                {"toxicity": 0.62, "insult_score": 0.65, "targeting_intensity": 0.61, "dominance_ratio": 0.58, "anger": 0.54},
                {"toxicity": 0.7, "insult_score": 0.72, "targeting_intensity": 0.68, "dominance_ratio": 0.64, "anger": 0.61},
                {"toxicity": 0.76, "insult_score": 0.79, "targeting_intensity": 0.77, "dominance_ratio": 0.71, "anger": 0.69, "risk_trend": "increasing"},
                {"toxicity": 0.79, "insult_score": 0.81, "targeting_intensity": 0.8, "dominance_ratio": 0.75, "anger": 0.72, "risk_trend": "increasing"},
            ],
        ),
    )
    assert decision.risk_type == "bullying"
    assert decision.postprocess_decision in {"follow_up", "notify_guardian"}


def test_bullying_weak_signal_discarded():
    decision = run_case(
        name="bullying_weak_signal",
        child_user_id="child-weak",
        conversation_id="conv-weak",
        chunk_id="current-weak",
        llm_result=build_llm_result(cyberbullying=0.55, grooming=0.2, self_harm=0.1, severity="low", confidence=0.52),
        current_metrics=build_metrics(
            toxicity=0.2,
            insult_score=0.22,
            anger=0.15,
            targeting_intensity=0.18,
            dominance_ratio=0.16,
            distress_signal=0.18,
            confidence=0.6,
        ),
        historical_metrics=build_historical("conv-weak", [{"toxicity": 0.14, "insult_score": 0.16}]),
    )
    assert decision.postprocess_decision == "discarded"
    assert decision.validated_risk is False


def test_grooming_acute_notify_guardian():
    decision = run_case(
        name="grooming_acute",
        child_user_id="child-2",
        conversation_id="conv-grooming",
        chunk_id="current-grooming",
        llm_result=build_llm_result(
            grooming=0.94,
            severity="high",
            confidence=0.93,
            key_evidence=["coercive intimacy cues", "control attempt"],
        ),
        current_metrics=build_metrics(
            toxicity=0.19,
            insult_score=0.1,
            anger=0.14,
            sadness=0.22,
            fear=0.71,
            manipulation_similarity=0.93,
            targeting_intensity=0.84,
            dominance_ratio=0.88,
            risk_trend="increasing",
            activity_anomaly=0.73,
            distress_signal=0.65,
            confidence=0.87,
        ),
        historical_metrics=build_historical(
            "conv-grooming",
            [
                {"manipulation_similarity": 0.41, "targeting_intensity": 0.38, "dominance_ratio": 0.35, "fear": 0.29},
                {"manipulation_similarity": 0.46, "targeting_intensity": 0.42, "dominance_ratio": 0.4, "fear": 0.31},
            ],
        ),
    )
    assert decision.risk_type == "grooming"
    assert decision.postprocess_decision == "notify_guardian"
    assert decision.notify_guardian is True


def test_grooming_short_history_still_high():
    decision = run_case(
        name="grooming_short_history",
        child_user_id="child-short",
        conversation_id="conv-short",
        chunk_id="current-short",
        llm_result=build_llm_result(grooming=0.96, severity="high", confidence=0.95),
        current_metrics=build_metrics(
            manipulation_similarity=0.97,
            targeting_intensity=0.89,
            dominance_ratio=0.91,
            fear=0.76,
            distress_signal=0.7,
            activity_anomaly=0.74,
            confidence=0.9,
            risk_trend="increasing",
        ),
        historical_metrics=[],
    )
    assert decision.postprocess_decision == "notify_guardian"
    assert decision.severity_band in {"high", "critical"}


def test_distress_isolated_follow_up():
    decision = run_case(
        name="distress_isolated",
        child_user_id="child-3",
        conversation_id="conv-distress",
        chunk_id="current-distress",
        llm_result=build_llm_result(self_harm=0.87, severity="medium", confidence=0.79, key_evidence=["hopelessness cue"]),
        current_metrics=build_metrics(
            toxicity=0.21,
            insult_score=0.14,
            anger=0.28,
            sadness=0.67,
            fear=0.54,
            manipulation_similarity=0.11,
            targeting_intensity=0.17,
            dominance_ratio=0.22,
            risk_trend="stable",
            activity_anomaly=0.43,
            distress_signal=0.61,
            confidence=0.76,
        ),
        historical_metrics=build_historical(
            "conv-distress",
            [
                {"distress_signal": 0.24, "sadness": 0.3, "fear": 0.22, "activity_anomaly": 0.18},
                {"distress_signal": 0.28, "sadness": 0.26, "fear": 0.2, "activity_anomaly": 0.21},
            ],
        ),
    )
    assert decision.risk_type == "distress"
    assert decision.notify_guardian is False
    assert decision.postprocess_decision == "follow_up"


def test_distress_chronic_stays_without_guardian_or_escalates():
    decision = run_case(
        name="distress_chronic",
        child_user_id="child-chronic",
        conversation_id="conv-distress-chronic",
        chunk_id="current-distress-chronic",
        llm_result=build_llm_result(self_harm=0.92, severity="high", confidence=0.9),
        current_metrics=build_metrics(
            sadness=0.9,
            fear=0.82,
            distress_signal=0.88,
            activity_anomaly=0.74,
            anger=0.2,
            risk_trend="increasing",
            confidence=0.85,
        ),
        historical_metrics=build_historical(
            "conv-distress-chronic",
            [
                {"distress_signal": 0.72, "sadness": 0.76, "fear": 0.66, "activity_anomaly": 0.5},
                {"distress_signal": 0.76, "sadness": 0.78, "fear": 0.7, "activity_anomaly": 0.55},
                {"distress_signal": 0.8, "sadness": 0.81, "fear": 0.74, "activity_anomaly": 0.6},
                {"distress_signal": 0.82, "sadness": 0.84, "fear": 0.76, "activity_anomaly": 0.64},
            ],
        ),
    )
    assert decision.risk_type == "distress"
    assert decision.postprocess_decision in {"follow_up", "notify_guardian"}


def test_existing_alert_same_level_no_new_alert():
    decision = run_case(
        name="existing_alert_same_level",
        child_user_id="child-alert",
        conversation_id="conv-alert",
        chunk_id="chunk-alert",
        llm_result=build_llm_result(grooming=0.95, severity="high", confidence=0.94),
        current_metrics=build_metrics(
            manipulation_similarity=0.95,
            targeting_intensity=0.87,
            dominance_ratio=0.89,
            fear=0.74,
            distress_signal=0.68,
            activity_anomaly=0.72,
            confidence=0.88,
            risk_trend="increasing",
        ),
        historical_metrics=build_historical("conv-alert", [{"manipulation_similarity": 0.5, "targeting_intensity": 0.44, "dominance_ratio": 0.42}]),
        existing_open_alerts=[
            {
                "id": "alert-1",
                "alert_type": "grooming",
                "alert_level": "high",
                "status": "open",
                "updated_at": "2026-04-10T10:00:00+00:00",
                "created_at": "2026-04-10T09:00:00+00:00",
            }
        ],
    )
    assert decision.create_new_alert is False


def test_existing_alert_escalation_update():
    decision = run_case(
        name="existing_alert_escalation",
        child_user_id="child-escalate",
        conversation_id="conv-escalate",
        chunk_id="chunk-escalate",
        llm_result=build_llm_result(grooming=0.99, severity="high", confidence=0.98),
        current_metrics=build_metrics(
            manipulation_similarity=0.99,
            targeting_intensity=0.94,
            dominance_ratio=0.95,
            fear=0.84,
            distress_signal=0.78,
            activity_anomaly=0.8,
            confidence=0.94,
            risk_trend="increasing",
        ),
        historical_metrics=build_historical(
            "conv-escalate",
            [
                {"manipulation_similarity": 0.62, "targeting_intensity": 0.5, "dominance_ratio": 0.48, "fear": 0.4},
                {"manipulation_similarity": 0.7, "targeting_intensity": 0.56, "dominance_ratio": 0.52, "fear": 0.46},
            ],
        ),
        existing_open_alerts=[
            {
                "id": "alert-2",
                "alert_type": "grooming",
                "alert_level": "medium",
                "status": "open",
                "updated_at": "2026-04-09T08:00:00+00:00",
                "created_at": "2026-04-09T07:00:00+00:00",
            }
        ],
    )
    assert decision.update_existing_alert is True or decision.create_new_alert is True


def test_parent_cooldown_blocks_repeat_notification():
    decision = run_case(
        name="guardian_cooldown",
        child_user_id="child-cooldown",
        conversation_id="conv-cooldown",
        chunk_id="chunk-cooldown",
        llm_result=build_llm_result(grooming=0.95, severity="high", confidence=0.95),
        current_metrics=build_metrics(
            manipulation_similarity=0.96,
            targeting_intensity=0.88,
            dominance_ratio=0.9,
            fear=0.8,
            distress_signal=0.74,
            activity_anomaly=0.76,
            confidence=0.91,
            risk_trend="increasing",
        ),
        historical_metrics=build_historical("conv-cooldown", [{"manipulation_similarity": 0.48, "targeting_intensity": 0.4, "dominance_ratio": 0.38}]),
        existing_open_alerts=[
            {
                "id": "alert-3",
                "alert_type": "grooming",
                "alert_level": "high",
                "status": "open",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    assert decision.notify_guardian is False or decision.severity_band == "critical"


def test_should_create_new_alert_helper():
    sample = PostprocessDecision(
        validated_risk=True,
        risk_type="bullying",
        severity_score=78,
        severity_band="high",
        postprocess_decision="notify_guardian",
        notify_guardian=True,
        notify_counselor=True,
        create_new_alert=False,
        update_existing_alert=False,
        trend_status="sustained_increase",
        score_breakdown=type("SB", (), {})(),  # dummy object, helper ignores it
        explanation="test",
    )
    assert should_create_new_alert([], sample) is True


def test_should_escalate_existing_alert_helper():
    sample = PostprocessDecision(
        validated_risk=True,
        risk_type="bullying",
        severity_score=96,
        severity_band="critical",
        postprocess_decision="notify_guardian",
        notify_guardian=True,
        notify_counselor=True,
        create_new_alert=False,
        update_existing_alert=False,
        trend_status="acute_jump",
        score_breakdown=type("SB", (), {})(),
        explanation="test",
    )
    assert should_escalate_existing_alert({"alert_level": "high"}, sample) is True


TESTS = {
    "normalize": test_normalize_llm_risk_type,
    "metric_type_selection": test_metric_type_selection_prefers_bullying,
    "intensity_bullying": test_bullying_intensity_high,
    "intensity_grooming": test_grooming_intensity_high,
    "intensity_distress": test_distress_intensity_moderate,
    "llm_support_bullying": test_llm_support_bullying_high,
    "llm_support_distress": test_llm_support_distress_medium,
    "llm_disagreement": test_llm_disagreement_can_still_favor_llm_when_metrics_are_not_decisive,
    "llm_push_close_call": test_llm_can_push_close_call_to_grooming,
    "trend_score_bullying": test_trend_score_rewards_rising_bullying,
    "final_type_scores": test_final_type_score_combines_metrics_llm_and_trend,
    "decreasing_distress": test_decreasing_trend_cools_down_distress_severity,
    "metrics_override_llm": test_metrics_override_moderate_llm_when_bullying_is_clear,
    "low_low_discarded": test_low_metrics_and_low_llm_stay_discarded,
    "follow_up_boundary": test_follow_up_boundary_stays_below_guardian,
    "notify_guardian_boundary": test_notify_guardian_boundary_crosses_70,
    "close_distress_llm": test_distress_llm_can_win_when_metrics_are_close,
    "grooming_decreasing": test_grooming_decreasing_trend_reduces_but_keeps_type,
    "bullying_existing_same_band": test_bullying_open_alert_not_escalated_when_same_band,
    "history_chronic": test_historical_escalation_chronic_high,
    "bullying_sustained": test_bullying_sustained_follow_up_or_guardian,
    "bullying_weak": test_bullying_weak_signal_discarded,
    "grooming_acute": test_grooming_acute_notify_guardian,
    "grooming_short_history": test_grooming_short_history_still_high,
    "distress_isolated": test_distress_isolated_follow_up,
    "distress_chronic": test_distress_chronic_stays_without_guardian_or_escalates,
    "existing_alert_same_level": test_existing_alert_same_level_no_new_alert,
    "existing_alert_escalation": test_existing_alert_escalation_update,
    "guardian_cooldown": test_parent_cooldown_blocks_repeat_notification,
    "helper_create_alert": test_should_create_new_alert_helper,
    "helper_escalate_alert": test_should_escalate_existing_alert_helper,
}


if __name__ == "__main__":
    selected = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    if selected == "all":
        passed = 0
        for name, runner in TESTS.items():
            print(f"\n=== {name} ===")
            runner()
            passed += 1
        print(f"\nPassed {passed} tests")
    else:
        if selected not in TESTS:
            raise SystemExit(f"Use one of: {', '.join(TESTS)} or 'all'")
        TESTS[selected]()
