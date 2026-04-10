from __future__ import annotations

from datetime import timezone

from .schemas import NormalizedMessage


def compute_risk_trend(
    messages: list[NormalizedMessage],
    toxicity_scores: list[float],
    *,
    positive_threshold: float = 0.03,
    negative_threshold: float = -0.03,
) -> str:
    if len(messages) < 2 or len(toxicity_scores) != len(messages):
        return "stable"

    slope = _linear_regression_slope(
        x_values=list(range(len(toxicity_scores))),
        y_values=toxicity_scores,
    )
    if slope > positive_threshold:
        return "increasing"
    if slope < negative_threshold:
        return "decreasing"
    return "stable"


def compute_activity_anomaly(messages: list[NormalizedMessage]) -> float:
    if not messages:
        return 0.0

    frequency_spike = _compute_frequency_spike(messages)
    late_night_flag = _compute_late_night_flag(messages)
    response_change = _compute_response_change(messages)
    score = 0.5 * frequency_spike + 0.3 * late_night_flag + 0.2 * response_change
    return round(min(1.0, score), 4)


def _compute_frequency_spike(messages: list[NormalizedMessage]) -> float:
    if len(messages) < 3:
        return 0.0

    timestamps = [message.timestamp.timestamp() for message in messages]
    duration_seconds = max(timestamps[-1] - timestamps[0], 1.0)
    messages_per_minute = len(messages) / (duration_seconds / 60.0)
    return min(1.0, messages_per_minute / 12.0)


def _compute_late_night_flag(messages: list[NormalizedMessage]) -> float:
    late_night_count = 0
    for message in messages:
        timestamp_utc = message.timestamp.astimezone(timezone.utc)
        if timestamp_utc.hour >= 23 or timestamp_utc.hour < 5:
            late_night_count += 1

    return late_night_count / len(messages)


def _compute_response_change(messages: list[NormalizedMessage]) -> float:
    if len(messages) < 4:
        return 0.0

    gaps = [
        max((current.timestamp - previous.timestamp).total_seconds(), 0.0)
        for previous, current in zip(messages, messages[1:])
    ]
    midpoint = max(1, len(gaps) // 2)
    first_half = gaps[:midpoint]
    second_half = gaps[midpoint:]
    if not second_half:
        return 0.0

    first_mean = sum(first_half) / len(first_half)
    second_mean = sum(second_half) / len(second_half)
    if first_mean <= 0:
        return 0.0

    relative_change = abs(second_mean - first_mean) / max(first_mean, 1.0)
    return min(1.0, relative_change)


def _linear_regression_slope(x_values: list[int], y_values: list[float]) -> float:
    count = len(x_values)
    mean_x = sum(x_values) / count
    mean_y = sum(y_values) / count

    numerator = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(x_values, y_values)
    )
    denominator = sum((x_value - mean_x) ** 2 for x_value in x_values)
    if denominator == 0:
        return 0.0

    return numerator / denominator
