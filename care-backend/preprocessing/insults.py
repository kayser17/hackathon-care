from __future__ import annotations

from .schemas import ToxicityArtifacts


def compute_insult_score(
    toxicity_artifacts: ToxicityArtifacts,
    *,
    insult_threshold: float = 0.7,
) -> float:
    if not toxicity_artifacts.per_message_scores:
        return 0.0

    insulting_messages = sum(
        score >= insult_threshold for score in toxicity_artifacts.per_message_scores
    )
    return round(insulting_messages / len(toxicity_artifacts.per_message_scores), 4)
