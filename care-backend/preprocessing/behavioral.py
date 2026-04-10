from __future__ import annotations

import re
from collections import defaultdict

from .schemas import NormalizedMessage


TARGETING_TOXICITY_THRESHOLD = 0.6
MENTION_CONFIDENCE = 1.0
PREVIOUS_SPEAKER_CONFIDENCE = 0.6


def compute_dominance_ratio(messages: list[NormalizedMessage]) -> float:
    if not messages:
        return 0.0

    counts_by_speaker: dict[str, int] = defaultdict(int)
    for message in messages:
        counts_by_speaker[message.speaker] += 1

    return round(max(counts_by_speaker.values()) / len(messages), 4)


def compute_targeting_intensity(
    messages: list[NormalizedMessage],
    toxicity_scores: list[float],
    *,
    toxicity_threshold: float = TARGETING_TOXICITY_THRESHOLD,
) -> float:
    if not messages or not toxicity_scores or len(messages) != len(toxicity_scores):
        return 0.0

    participants = sorted({message.speaker for message in messages})
    harmful_received_by_target: dict[str, float] = defaultdict(float)
    aggressors_by_target: dict[str, set[str]] = defaultdict(set)
    total_harmful_weight = 0.0

    for index, (message, toxicity_score) in enumerate(zip(messages, toxicity_scores)):
        if toxicity_score < toxicity_threshold:
            continue

        target, target_confidence = infer_message_target(
            message=message,
            participants=participants,
            previous_message=messages[index - 1] if index > 0 else None,
        )
        if target is None:
            continue

        weighted_harm = float(toxicity_score) * float(target_confidence)
        harmful_received_by_target[target] += weighted_harm
        aggressors_by_target[target].add(message.speaker)
        total_harmful_weight += weighted_harm

    if total_harmful_weight <= 0:
        return 0.0

    concentration_score = max(harmful_received_by_target.values()) / total_harmful_weight
    pile_on_score = 0.0
    if len(participants) > 2:
        pile_on_score = max(
            (
                max(len(aggressors) - 1, 0) / max(len(participants) - 2, 1)
                for aggressors in aggressors_by_target.values()
            ),
            default=0.0,
        )

    targeting_intensity = 0.85 * concentration_score + 0.15 * pile_on_score
    return round(min(1.0, targeting_intensity), 4)


def infer_message_target(
    *,
    message: NormalizedMessage,
    participants: list[str],
    previous_message: NormalizedMessage | None,
) -> tuple[str | None, float]:
    mentioned_target = _match_participant_name(message.normalized_text, message.speaker, participants)
    if mentioned_target is not None:
        return mentioned_target, MENTION_CONFIDENCE

    if previous_message is not None and previous_message.speaker != message.speaker:
        return previous_message.speaker, PREVIOUS_SPEAKER_CONFIDENCE

    return None, 0.0


def _match_participant_name(
    text: str,
    current_speaker: str,
    participants: list[str],
) -> str | None:
    lowered_text = text.lower()
    for participant in participants:
        if participant == current_speaker:
            continue

        for alias in _speaker_aliases(participant):
            pattern = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)")
            if pattern.search(lowered_text):
                return participant
    return None


def _speaker_aliases(participant: str) -> set[str]:
    lowered = participant.lower()
    aliases = {lowered, f"@{lowered}"}
    normalized = lowered.replace("_", " ").replace("-", " ")
    aliases.add(normalized)
    aliases.add(f"@{normalized}")
    for token in normalized.split():
        if token:
            aliases.add(token)
            aliases.add(f"@{token}")
    return aliases
