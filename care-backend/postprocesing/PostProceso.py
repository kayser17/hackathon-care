from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Protocol


class RiskType(str, Enum):
    BULLYING = "bullying"
    GROOMING = "grooming"
    DISTRESS = "distress"


class SeverityBand(str, Enum):
    NONE = "none"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionLevel(str, Enum):
    DISCARDED = "discarded"
    FOLLOW_UP = "follow_up"
    NOTIFY_GUARDIAN = "notify_guardian"


class TrendStatus(str, Enum):
    ISOLATED_SPIKE = "isolated_spike"
    SUSTAINED_INCREASE = "sustained_increase"
    ACUTE_JUMP = "acute_jump"
    CHRONIC_HIGH = "chronic_high"
    INSUFFICIENT_HISTORY = "insufficient_history"


class LLMRiskType(str, Enum):
    CYBERBULLYING = "cyberbullying"
    GROOMING = "grooming"
    SELF_HARM = "self_harm"


DEFAULT_MODEL_NAME = "postprocess-v1"
SHORT_WINDOW = 3
MID_WINDOW = 7
BASELINE_WINDOW = 14
HIGH_INTENSITY_THRESHOLD = 0.75
VERY_HIGH_INTENSITY_THRESHOLD = 0.88
HIGH_ALIGNMENT_THRESHOLD = 0.72
SUSTAINED_RATIO_HIGH = 0.60
ACUTE_DELTA_THRESHOLD = 0.22
CHRONIC_HIGH_MEAN_THRESHOLD = 0.72
PARENT_NOTIFICATION_COOLDOWN_HOURS = 12
TYPE_CLASSIFICATION_THRESHOLD = 0.42
DISCARD_THRESHOLD = 0.45
MONITOR_THRESHOLD = 0.60
REVIEW_THRESHOLD = 0.75
HIGH_THRESHOLD = 0.88

RISK_TYPE_MAP: dict[str, RiskType] = {
    LLMRiskType.CYBERBULLYING.value: RiskType.BULLYING,
    LLMRiskType.GROOMING.value: RiskType.GROOMING,
    LLMRiskType.SELF_HARM.value: RiskType.DISTRESS,
}

SEVERITY_BAND_RANK = {
    SeverityBand.NONE: 0,
    SeverityBand.MEDIUM: 1,
    SeverityBand.HIGH: 2,
    SeverityBand.CRITICAL: 3,
}

DECISION_LEVEL_RANK = {
    DecisionLevel.DISCARDED: 0,
    DecisionLevel.FOLLOW_UP: 1,
    DecisionLevel.NOTIFY_GUARDIAN: 2,
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def safe_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


@dataclass(slots=True)
class EmotionMetrics:
    anger: float = 0.0
    sadness: float = 0.0
    fear: float = 0.0


@dataclass(slots=True)
class LLMResult:
    risk_detected: bool
    risk_types: dict[str, float]
    severity: str
    confidence: float
    key_evidence: list[str] = field(default_factory=list)
    reasoning: str = ""
    conversation_summary: str = ""


@dataclass(slots=True)
class PreprocessingMetrics:
    toxicity: float = 0.0
    insult_score: float = 0.0
    emotion: EmotionMetrics = field(default_factory=EmotionMetrics)
    manipulation_similarity: float = 0.0
    targeting_intensity: float = 0.0
    dominance_ratio: float = 0.0
    risk_trend: str = "stable"
    activity_anomaly: float = 0.0
    distress_signal: float = 0.0
    confidence: float = 0.0


@dataclass(slots=True)
class HistoricalChunkMetrics:
    chunk_id: str
    conversation_id: str
    created_at: Optional[datetime] = None
    toxicity: float = 0.0
    insult_score: float = 0.0
    manipulation_similarity: float = 0.0
    targeting_intensity: float = 0.0
    dominance_ratio: float = 0.0
    activity_anomaly: float = 0.0
    distress_signal: float = 0.0
    confidence: float = 0.0
    risk_trend: str = "stable"
    emotion_anger: float = 0.0
    emotion_sadness: float = 0.0
    emotion_fear: float = 0.0

    def as_preprocessing_metrics(self) -> PreprocessingMetrics:
        return PreprocessingMetrics(
            toxicity=self.toxicity,
            insult_score=self.insult_score,
            emotion=EmotionMetrics(
                anger=self.emotion_anger,
                sadness=self.emotion_sadness,
                fear=self.emotion_fear,
            ),
            manipulation_similarity=self.manipulation_similarity,
            targeting_intensity=self.targeting_intensity,
            dominance_ratio=self.dominance_ratio,
            risk_trend=self.risk_trend,
            activity_anomaly=self.activity_anomaly,
            distress_signal=self.distress_signal,
            confidence=self.confidence,
        )


@dataclass(slots=True)
class ScoreBreakdown:
    metric_type_score: float
    llm_type_score: float
    trend_type_score: float
    final_type_score: float
    current_intensity: float
    historical_escalation_score: float
    llm_support_score: float
    llm_confidence: float
    preprocessing_confidence: float
    combined_confidence: float
    final_score: float
    recent_mean: float
    baseline_mean: float
    delta_vs_baseline: float
    sustained_ratio: float
    consecutive_high: int
    slope: float


@dataclass(slots=True)
class PostprocessDecision:
    validated_risk: bool
    risk_type: Optional[str]
    severity_score: int
    severity_band: str
    postprocess_decision: str
    notify_guardian: bool
    notify_counselor: bool
    create_new_alert: bool
    update_existing_alert: bool
    trend_status: str
    score_breakdown: ScoreBreakdown
    explanation: str
    risk_assessment_payload: Optional[dict[str, Any]] = None
    alert_payload: Optional[dict[str, Any]] = None
    alert_action_payload: Optional[dict[str, Any]] = None


class RepositoryProtocol(Protocol):
    def get_current_chunk_metrics(self, chunk_id: str) -> Optional[PreprocessingMetrics]:
        ...

    def get_historical_metrics_for_conversation(
        self,
        conversation_id: str,
        current_chunk_id: str,
        limit: int = BASELINE_WINDOW,
    ) -> list[HistoricalChunkMetrics]:
        ...

    def get_open_alerts_for_conversation(
        self,
        child_user_id: str,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        ...

    def get_recent_risk_assessments(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        ...


SQL_GET_CURRENT_CHUNK_METRICS = """
SELECT cm.chunk_id, cm.toxicity, cm.insult_score, cm.manipulation_similarity,
       cm.targeting_intensity, cm.dominance_ratio, cm.activity_anomaly,
       cm.distress_signal, cm.confidence, cm.risk_trend, cm.emotion_anger,
       cm.emotion_sadness, cm.emotion_fear, cm.pipeline_version, cm.created_at
FROM chunk_metrics cm
WHERE cm.chunk_id = %(chunk_id)s;
""".strip()

SQL_GET_HISTORICAL_METRICS = """
SELECT cc.id AS chunk_id, cc.conversation_id, cm.created_at, cm.toxicity,
       cm.insult_score, cm.manipulation_similarity, cm.targeting_intensity,
       cm.dominance_ratio, cm.activity_anomaly, cm.distress_signal,
       cm.confidence, cm.risk_trend, cm.emotion_anger, cm.emotion_sadness,
       cm.emotion_fear
FROM conversation_chunks cc
JOIN chunk_metrics cm ON cm.chunk_id = cc.id
WHERE cc.conversation_id = %(conversation_id)s
  AND cc.id <> %(current_chunk_id)s
ORDER BY cc.chunk_end_at DESC
LIMIT %(limit)s;
""".strip()

SQL_GET_OPEN_ALERTS = """
SELECT a.id, a.child_user_id, a.conversation_id, a.chunk_id, a.risk_assessment_id,
       a.alert_type, a.alert_level, a.title, a.summary, a.status, a.created_at,
       a.updated_at
FROM alerts a
WHERE a.child_user_id = %(child_user_id)s
  AND a.conversation_id = %(conversation_id)s
  AND a.status IN ('open', 'investigating', 'pending');
""".strip()

SQL_GET_RECENT_RISK_ASSESSMENTS = """
SELECT ra.id, ra.chunk_id, ra.risk_type, ra.risk_level, ra.severity_score,
       ra.confidence_score, ra.rationale, ra.model_name, ra.created_at
FROM risk_assessments ra
JOIN conversation_chunks cc ON cc.id = ra.chunk_id
WHERE cc.conversation_id = %(conversation_id)s
ORDER BY ra.created_at DESC
LIMIT %(limit)s;
""".strip()


class RepositoryStub:
    def get_current_chunk_metrics(self, chunk_id: str) -> Optional[PreprocessingMetrics]:
        return None

    def get_historical_metrics_for_conversation(
        self,
        conversation_id: str,
        current_chunk_id: str,
        limit: int = BASELINE_WINDOW,
    ) -> list[HistoricalChunkMetrics]:
        return []

    def get_open_alerts_for_conversation(
        self,
        child_user_id: str,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def get_recent_risk_assessments(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return []


def get_current_chunk_metrics(repository: RepositoryProtocol, chunk_id: str) -> Optional[PreprocessingMetrics]:
    return repository.get_current_chunk_metrics(chunk_id)


def get_historical_metrics_for_conversation(
    repository: RepositoryProtocol,
    conversation_id: str,
    current_chunk_id: str,
    limit: int = BASELINE_WINDOW,
) -> list[HistoricalChunkMetrics]:
    return repository.get_historical_metrics_for_conversation(conversation_id, current_chunk_id, limit)


def get_open_alerts_for_conversation(
    repository: RepositoryProtocol,
    child_user_id: str,
    conversation_id: str,
) -> list[dict[str, Any]]:
    return repository.get_open_alerts_for_conversation(child_user_id, conversation_id)


def get_recent_risk_assessments(
    repository: RepositoryProtocol,
    conversation_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return repository.get_recent_risk_assessments(conversation_id, limit)


def normalize_llm_risk_type(llm_result: LLMResult) -> Optional[str]:
    if not llm_result.risk_types:
        return None
    dominant_type, dominant_score = max(llm_result.risk_types.items(), key=lambda item: item[1])
    if dominant_score <= 0.0:
        return None
    mapped = RISK_TYPE_MAP.get(dominant_type)
    return mapped.value if mapped else None


def compute_type_scores(metrics: PreprocessingMetrics) -> dict[str, float]:
    anger = metrics.emotion.anger
    sadness = metrics.emotion.sadness
    fear = metrics.emotion.fear
    return {
        RiskType.BULLYING.value: clamp(
            (metrics.toxicity * 0.25)
            + (metrics.insult_score * 0.25)
            + (metrics.targeting_intensity * 0.19)
            + (metrics.dominance_ratio * 0.12)
            + (anger * 0.10)
            + (metrics.activity_anomaly * 0.05)
            + (metrics.distress_signal * 0.04)
        ),
        RiskType.GROOMING.value: clamp(
            (metrics.manipulation_similarity * 0.31)
            + (metrics.targeting_intensity * 0.18)
            + (metrics.dominance_ratio * 0.16)
            + (fear * 0.12)
            + (metrics.activity_anomaly * 0.09)
            + (metrics.distress_signal * 0.08)
            + (metrics.confidence * 0.06)
        ),
        RiskType.DISTRESS.value: clamp(
            (metrics.distress_signal * 0.30)
            + (sadness * 0.23)
            + (fear * 0.16)
            + (metrics.activity_anomaly * 0.12)
            + (anger * 0.08)
            + (metrics.toxicity * 0.06)
            + (metrics.insult_score * 0.05)
        ),
    }


def select_risk_type(metrics: PreprocessingMetrics) -> tuple[Optional[str], dict[str, float]]:
    type_scores = compute_type_scores(metrics)
    risk_type, score = max(type_scores.items(), key=lambda item: item[1])
    if score < TYPE_CLASSIFICATION_THRESHOLD:
        return None, type_scores
    return risk_type, type_scores


def compute_current_intensity(risk_type: str, metrics: PreprocessingMetrics) -> float:
    type_scores = compute_type_scores(metrics)
    trend_adjustment = {"increasing": 0.06, "stable": 0.0, "decreasing": -0.06}.get(metrics.risk_trend, 0.0)
    return clamp(type_scores[risk_type] + trend_adjustment)


def compute_llm_type_scores(llm_result: LLMResult) -> dict[str, float]:
    return {
        RiskType.BULLYING.value: clamp(llm_result.risk_types.get(LLMRiskType.CYBERBULLYING.value, 0.0)),
        RiskType.GROOMING.value: clamp(llm_result.risk_types.get(LLMRiskType.GROOMING.value, 0.0)),
        RiskType.DISTRESS.value: clamp(llm_result.risk_types.get(LLMRiskType.SELF_HARM.value, 0.0)),
    }


def compute_llm_support_score(
    risk_type: str,
    llm_result: LLMResult,
) -> float:
    llm_key_by_risk_type = {
        RiskType.BULLYING.value: LLMRiskType.CYBERBULLYING.value,
        RiskType.GROOMING.value: LLMRiskType.GROOMING.value,
        RiskType.DISTRESS.value: LLMRiskType.SELF_HARM.value,
    }
    llm_key = llm_key_by_risk_type[risk_type]
    selected_type_probability = llm_result.risk_types.get(llm_key, 0.0)
    dominant_llm_type = normalize_llm_risk_type(llm_result)
    agreement_bonus = 0.10 if dominant_llm_type == risk_type else -0.08 if dominant_llm_type else 0.0
    evidence_bonus = clamp(len(llm_result.key_evidence) / 5.0, 0.0, 0.10)
    severity_bonus = {"low": 0.0, "medium": 0.04, "high": 0.08}.get(llm_result.severity.lower(), 0.0)
    detected_bonus = 0.03 if llm_result.risk_detected else 0.0
    return clamp((selected_type_probability * 0.62) + (llm_result.confidence * 0.17) + agreement_bonus + evidence_bonus + severity_bonus + detected_bonus)


def _historical_series_by_risk_type(
    risk_type: str,
    historical_metrics: list[HistoricalChunkMetrics],
) -> list[float]:
    ordered = sorted(
        historical_metrics,
        key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc),
    )
    return [compute_current_intensity(risk_type, item.as_preprocessing_metrics()) for item in ordered]


def compute_historical_escalation(
    risk_type: str,
    current_metrics: PreprocessingMetrics,
    historical_metrics: list[HistoricalChunkMetrics],
) -> dict[str, Any]:
    series = _historical_series_by_risk_type(risk_type, historical_metrics)
    current_intensity = compute_current_intensity(risk_type, current_metrics)
    full_series = series + [current_intensity]
    recent_window = full_series[-SHORT_WINDOW:]
    medium_window = full_series[-MID_WINDOW:]
    baseline_window = full_series[-BASELINE_WINDOW - 1 : -1] if len(full_series) > 1 else []
    recent_mean = safe_mean(recent_window)
    baseline_mean = safe_mean(baseline_window) if baseline_window else safe_mean(full_series[:-1])
    delta_vs_baseline = recent_mean - baseline_mean
    sustained_ratio = (
        len([value for value in medium_window if value >= HIGH_INTENSITY_THRESHOLD]) / len(medium_window)
        if medium_window
        else 0.0
    )

    consecutive_high = 0
    for value in reversed(full_series):
        if value >= HIGH_INTENSITY_THRESHOLD:
            consecutive_high += 1
        else:
            break

    slope = 0.0
    if len(recent_window) >= 2:
        slope = (recent_window[-1] - recent_window[0]) / (len(recent_window) - 1)

    if len(full_series) < 3:
        trend_status = TrendStatus.INSUFFICIENT_HISTORY
    elif recent_mean >= CHRONIC_HIGH_MEAN_THRESHOLD and sustained_ratio >= SUSTAINED_RATIO_HIGH:
        trend_status = TrendStatus.CHRONIC_HIGH
    elif delta_vs_baseline >= ACUTE_DELTA_THRESHOLD and current_intensity >= VERY_HIGH_INTENSITY_THRESHOLD:
        trend_status = TrendStatus.ACUTE_JUMP
    elif delta_vs_baseline >= 0.12 and sustained_ratio >= 0.50:
        trend_status = TrendStatus.SUSTAINED_INCREASE
    else:
        trend_status = TrendStatus.ISOLATED_SPIKE

    escalation_score = clamp(
        (recent_mean * 0.30)
        + (clamp(delta_vs_baseline + 0.5) * 0.22)
        + (sustained_ratio * 0.22)
        + (clamp(consecutive_high / 4.0) * 0.16)
        + (clamp((slope + 0.2) / 0.4) * 0.10)
    )
    return {
        "recent_mean": recent_mean,
        "baseline_mean": baseline_mean,
        "delta_vs_baseline": delta_vs_baseline,
        "sustained_ratio": sustained_ratio,
        "consecutive_high": consecutive_high,
        "slope": slope,
        "trend_status": trend_status.value,
        "historical_escalation_score": escalation_score,
    }


def compute_trend_type_score(
    risk_type: str,
    current_metrics: PreprocessingMetrics,
    historical_metrics: list[HistoricalChunkMetrics],
) -> tuple[float, dict[str, Any]]:
    historical = compute_historical_escalation(risk_type, current_metrics, historical_metrics)
    trend_direction_bonus = {
        "increasing": 0.08,
        "stable": 0.0,
        "decreasing": -0.08,
    }.get(current_metrics.risk_trend, 0.0)
    trend_type_score = clamp((historical["historical_escalation_score"] * 0.75) + trend_direction_bonus)
    return trend_type_score, historical


def compute_final_type_scores(
    metric_scores: dict[str, float],
    llm_scores: dict[str, float],
    trend_scores: dict[str, float],
) -> dict[str, float]:
    return {
        risk_type: clamp(
            (metric_scores[risk_type] * 0.45)
            + (llm_scores[risk_type] * 0.35)
            + (trend_scores[risk_type] * 0.20)
        )
        for risk_type in metric_scores
    }


def compute_final_alert_score(
    current_intensity: float,
    historical_escalation_score: float,
    llm_support_score: float,
    llm_confidence: float,
    preprocessing_confidence: float,
) -> float:
    combined_confidence = clamp((llm_confidence * 0.55) + (preprocessing_confidence * 0.45))
    return clamp(
        (current_intensity * 0.45)
        + (historical_escalation_score * 0.20)
        + (llm_support_score * 0.25)
        + (combined_confidence * 0.10)
    )


def _decision_level_from_score(score: float) -> DecisionLevel:
    if score < DISCARD_THRESHOLD:
        return DecisionLevel.DISCARDED
    if score < 0.70:
        return DecisionLevel.FOLLOW_UP
    return DecisionLevel.NOTIFY_GUARDIAN


def _severity_band_from_score(score: float) -> SeverityBand:
    if score < DISCARD_THRESHOLD:
        return SeverityBand.NONE
    if score < 0.70:
        return SeverityBand.MEDIUM
    if score < 0.90:
        return SeverityBand.HIGH
    return SeverityBand.CRITICAL


def _severity_score_percent(score: float) -> int:
    return max(0, min(100, round(score * 100)))


def _guardian_cooldown_active(existing_open_alerts: list[dict[str, Any]], risk_type: str) -> bool:
    now = datetime.now(timezone.utc)
    for alert in existing_open_alerts:
        if alert.get("alert_type") != risk_type:
            continue
        updated_at = safe_datetime(alert.get("updated_at")) or safe_datetime(alert.get("created_at"))
        if updated_at and now - updated_at <= timedelta(hours=PARENT_NOTIFICATION_COOLDOWN_HOURS):
            return True
    return False


def should_create_new_alert(existing_open_alerts: list[dict[str, Any]], decision: PostprocessDecision) -> bool:
    if not decision.validated_risk or decision.severity_band == SeverityBand.NONE.value or not decision.risk_type:
        return False
    same_type_alerts = [
        alert
        for alert in existing_open_alerts
        if alert.get("alert_type") == decision.risk_type and alert.get("status") in {"open", "investigating", "pending"}
    ]
    if not same_type_alerts:
        return True
    current_rank = SEVERITY_BAND_RANK[SeverityBand(decision.severity_band)]
    highest_existing = max(SEVERITY_BAND_RANK[SeverityBand(alert.get("alert_level", SeverityBand.NONE.value))] for alert in same_type_alerts)
    return current_rank > highest_existing


def should_escalate_existing_alert(existing_alert: dict[str, Any], decision: PostprocessDecision) -> bool:
    existing_level = SeverityBand(existing_alert.get("alert_level", SeverityBand.NONE.value))
    decision_level = SeverityBand(decision.severity_band)
    return SEVERITY_BAND_RANK[decision_level] > SEVERITY_BAND_RANK[existing_level]


def _select_target_alert(existing_open_alerts: list[dict[str, Any]], risk_type: Optional[str]) -> Optional[dict[str, Any]]:
    if not risk_type:
        return None
    matching = [alert for alert in existing_open_alerts if alert.get("alert_type") == risk_type]
    if not matching:
        return None
    matching.sort(
        key=lambda item: safe_datetime(item.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return matching[0]


def _build_explanation(
    risk_type: str,
    severity_band: SeverityBand,
    historical: dict[str, Any],
    metrics: PreprocessingMetrics,
    metric_type_score: float,
    llm_support_score: float,
    notify_guardian: bool,
    notify_counselor: bool,
) -> str:
    if risk_type == RiskType.BULLYING.value:
        base = (
            f"{severity_band.value.capitalize()} bullying profile driven by metric weights on toxicity, insults and targeting intensity, "
            f"with an {metrics.risk_trend} short-term trend."
        )
    elif risk_type == RiskType.GROOMING.value:
        base = (
            "Grooming profile driven by manipulation similarity, dominance ratio and targeted interaction pattern."
        )
    else:
        base = (
            "Distress profile driven by sadness, fear and distress signal."
            if not notify_guardian
            else "High distress profile with sustained emotional and behavioral deterioration."
        )
    details = [
        f"Metric type score {metric_type_score:.2f}.",
        f"Temporal pattern classified as {historical['trend_status']}.",
        f"LLM support contribution {llm_support_score:.2f}.",
    ]
    if notify_guardian:
        details.append("Guardian notification enabled.")
    if notify_counselor:
        details.append("Counselor review enabled.")
    return f"{base} {' '.join(details)}"


def _build_risk_assessment_payload(
    *,
    chunk_id: str,
    risk_type: str,
    severity_band: str,
    final_score: float,
    confidence_score: float,
    explanation: str,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "risk_type": risk_type,
        "severity_band": severity_band,
        "severity_score": _severity_score_percent(final_score),
        "confidence_score": round(confidence_score, 4),
        "rationale": explanation,
        "model_name": DEFAULT_MODEL_NAME,
    }


def _build_alert_payload(
    *,
    child_user_id: str,
    conversation_id: str,
    chunk_id: str,
    risk_type: str,
    severity_band: str,
    explanation: str,
) -> dict[str, Any]:
    return {
        "child_user_id": child_user_id,
        "conversation_id": conversation_id,
        "chunk_id": chunk_id,
        "alert_type": risk_type,
        "severity_band": severity_band,
        "title": f"{risk_type.capitalize()} risk {severity_band}",
        "summary": explanation,
        "status": "open",
    }


def _build_alert_action_payload(
    *,
    action: str,
    target_alert_id: Optional[str],
    notify_guardian: bool,
    notify_counselor: bool,
    explanation: str,
) -> dict[str, Any]:
    return {
        "alert_id": target_alert_id,
        "action_type": action,
        "notify_guardian": notify_guardian,
        "notify_counselor": notify_counselor,
        "notes": explanation,
    }


def decide_alert_level(
    *,
    risk_type: str,
    llm_result: LLMResult,
    current_metrics: PreprocessingMetrics,
    metric_type_score: float,
    llm_type_score: float,
    trend_type_score: float,
    final_type_score: float,
    final_score: float,
    current_intensity: float,
    llm_support_score: float,
    historical: dict[str, Any],
    existing_open_alerts: Optional[list[dict[str, Any]]] = None,
) -> PostprocessDecision:
    existing_open_alerts = existing_open_alerts or []
    decision_level = _decision_level_from_score(final_score)
    severity_band = _severity_band_from_score(final_score)
    severity_score = _severity_score_percent(final_score)
    validated_risk = decision_level != DecisionLevel.DISCARDED
    notify_guardian = False
    notify_counselor = decision_level in {DecisionLevel.FOLLOW_UP, DecisionLevel.NOTIFY_GUARDIAN}

    if risk_type == RiskType.GROOMING.value:
        if current_intensity >= 0.82 and (metric_type_score >= 0.75 or llm_support_score >= HIGH_ALIGNMENT_THRESHOLD):
            validated_risk = True
            if SEVERITY_BAND_RANK[severity_band] < SEVERITY_BAND_RANK[SeverityBand.HIGH]:
                severity_band = SeverityBand.HIGH
            if DECISION_LEVEL_RANK[decision_level] < DECISION_LEVEL_RANK[DecisionLevel.NOTIFY_GUARDIAN]:
                decision_level = DecisionLevel.NOTIFY_GUARDIAN
            notify_guardian = True
            notify_counselor = True
    elif risk_type == RiskType.DISTRESS.value:
        if historical["trend_status"] in {TrendStatus.SUSTAINED_INCREASE.value, TrendStatus.CHRONIC_HIGH.value} and final_score >= REVIEW_THRESHOLD:
            notify_counselor = True
        if historical["trend_status"] in {TrendStatus.ACUTE_JUMP.value, TrendStatus.CHRONIC_HIGH.value} and final_score >= HIGH_THRESHOLD:
            notify_guardian = True
            notify_counselor = True
        else:
            notify_guardian = False
    elif risk_type == RiskType.BULLYING.value:
        repeated_pattern = historical["sustained_ratio"] >= 0.50 or historical["consecutive_high"] >= 2
        if (current_intensity >= HIGH_INTENSITY_THRESHOLD and repeated_pattern) or (
            severity_band in {SeverityBand.HIGH, SeverityBand.CRITICAL} and repeated_pattern
        ):
            notify_guardian = True
            notify_counselor = True
        else:
            notify_counselor = notify_counselor or validated_risk

    if decision_level == DecisionLevel.DISCARDED:
        validated_risk = False
        notify_counselor = False
        notify_guardian = False
        severity_band = SeverityBand.NONE
    elif decision_level == DecisionLevel.FOLLOW_UP:
        notify_guardian = False
        if severity_band == SeverityBand.CRITICAL:
            severity_band = SeverityBand.HIGH

    cooldown_active = _guardian_cooldown_active(existing_open_alerts, risk_type) if notify_guardian else False
    if cooldown_active and severity_band != SeverityBand.CRITICAL:
        notify_guardian = False

    explanation = _build_explanation(
        risk_type=risk_type,
        severity_band=severity_band,
        historical=historical,
        metrics=current_metrics,
        metric_type_score=metric_type_score,
        llm_support_score=llm_support_score,
        notify_guardian=notify_guardian,
        notify_counselor=notify_counselor,
    )
    combined_confidence = clamp((llm_result.confidence * 0.55) + (current_metrics.confidence * 0.45))
    score_breakdown = ScoreBreakdown(
        metric_type_score=round(metric_type_score, 4),
        llm_type_score=round(llm_type_score, 4),
        trend_type_score=round(trend_type_score, 4),
        final_type_score=round(final_type_score, 4),
        current_intensity=round(current_intensity, 4),
        historical_escalation_score=round(historical["historical_escalation_score"], 4),
        llm_support_score=round(llm_support_score, 4),
        llm_confidence=round(llm_result.confidence, 4),
        preprocessing_confidence=round(current_metrics.confidence, 4),
        combined_confidence=round(combined_confidence, 4),
        final_score=round(final_score, 4),
        recent_mean=round(historical["recent_mean"], 4),
        baseline_mean=round(historical["baseline_mean"], 4),
        delta_vs_baseline=round(historical["delta_vs_baseline"], 4),
        sustained_ratio=round(historical["sustained_ratio"], 4),
        consecutive_high=historical["consecutive_high"],
        slope=round(historical["slope"], 4),
    )
    return PostprocessDecision(
        validated_risk=validated_risk,
        risk_type=risk_type if validated_risk else None,
        severity_score=severity_score,
        severity_band=severity_band.value,
        postprocess_decision=decision_level.value,
        notify_guardian=notify_guardian,
        notify_counselor=notify_counselor,
        create_new_alert=False,
        update_existing_alert=False,
        trend_status=historical["trend_status"],
        score_breakdown=score_breakdown,
        explanation=explanation,
    )


def process_llm_true_result(
    *,
    child_user_id: str,
    conversation_id: str,
    chunk_id: str,
    llm_result: LLMResult,
    current_metrics: PreprocessingMetrics,
    historical_metrics: list[HistoricalChunkMetrics],
    existing_open_alerts: list[dict[str, Any]] | None = None,
) -> PostprocessDecision:
    metric_scores = compute_type_scores(current_metrics)
    llm_type_scores = compute_llm_type_scores(llm_result)
    trend_scores: dict[str, float] = {}
    historical_by_type: dict[str, dict[str, Any]] = {}
    for risk_type_name in metric_scores:
        trend_score, historical = compute_trend_type_score(risk_type_name, current_metrics, historical_metrics)
        trend_scores[risk_type_name] = trend_score
        historical_by_type[risk_type_name] = historical

    final_type_scores = compute_final_type_scores(metric_scores, llm_type_scores, trend_scores)
    risk_type, final_type_score = max(final_type_scores.items(), key=lambda item: item[1])
    if final_type_score < TYPE_CLASSIFICATION_THRESHOLD:
        combined_confidence = clamp((llm_result.confidence * 0.55) + (current_metrics.confidence * 0.45))
        breakdown = ScoreBreakdown(
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            round(max(compute_llm_type_scores(llm_result).values(), default=0.0), 4),
            round(llm_result.confidence, 4),
            round(current_metrics.confidence, 4),
            round(combined_confidence, 4),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0,
            0.0,
        )
        return PostprocessDecision(
            validated_risk=False,
            risk_type=None,
            severity_score=0,
            severity_band=SeverityBand.NONE.value,
            postprocess_decision=DecisionLevel.DISCARDED.value,
            notify_guardian=False,
            notify_counselor=False,
            create_new_alert=False,
            update_existing_alert=False,
            trend_status=TrendStatus.INSUFFICIENT_HISTORY.value,
            score_breakdown=breakdown,
            explanation="The weighted metrics do not support classifying this chunk as bullying, grooming or distress with enough intensity.",
        )

    existing_open_alerts = existing_open_alerts or []
    metric_type_score = metric_scores[risk_type]
    llm_type_score = llm_type_scores[risk_type]
    trend_type_score = trend_scores[risk_type]
    current_intensity = compute_current_intensity(risk_type, current_metrics)
    llm_support_score = compute_llm_support_score(risk_type, llm_result)
    historical = historical_by_type[risk_type]
    final_score = compute_final_alert_score(
        current_intensity=current_intensity,
        historical_escalation_score=historical["historical_escalation_score"],
        llm_support_score=llm_support_score,
        llm_confidence=llm_result.confidence,
        preprocessing_confidence=current_metrics.confidence,
    )
    decision = decide_alert_level(
        risk_type=risk_type,
        llm_result=llm_result,
        current_metrics=current_metrics,
        metric_type_score=metric_type_score,
        llm_type_score=llm_type_score,
        trend_type_score=trend_type_score,
        final_type_score=final_type_score,
        final_score=final_score,
        current_intensity=current_intensity,
        llm_support_score=llm_support_score,
        historical=historical,
        existing_open_alerts=existing_open_alerts,
    )

    target_alert = _select_target_alert(existing_open_alerts, decision.risk_type)
    decision.create_new_alert = should_create_new_alert(existing_open_alerts, decision)
    decision.update_existing_alert = bool(target_alert and should_escalate_existing_alert(target_alert, decision))

    combined_confidence = clamp((llm_result.confidence * 0.55) + (current_metrics.confidence * 0.45))
    if decision.validated_risk and decision.risk_type:
        decision.risk_assessment_payload = _build_risk_assessment_payload(
            chunk_id=chunk_id,
            risk_type=decision.risk_type,
            severity_band=decision.severity_band,
            final_score=decision.score_breakdown.final_score,
            confidence_score=combined_confidence,
            explanation=decision.explanation,
        )

    if decision.severity_band != SeverityBand.NONE.value and (decision.create_new_alert or decision.update_existing_alert) and decision.risk_type:
        decision.alert_payload = _build_alert_payload(
            child_user_id=child_user_id,
            conversation_id=conversation_id,
            chunk_id=chunk_id,
            risk_type=decision.risk_type,
            severity_band=decision.severity_band,
            explanation=decision.explanation,
        )
        decision.alert_action_payload = _build_alert_action_payload(
            action="create_alert" if decision.create_new_alert else "update_alert",
            target_alert_id=target_alert.get("id") if target_alert else None,
            notify_guardian=decision.notify_guardian,
            notify_counselor=decision.notify_counselor,
            explanation=decision.explanation,
        )
    return decision
