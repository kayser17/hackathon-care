"""Central orchestrator that sequences: preprocessing → LLM → postprocessing → alert → broadcast."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.runner import LLMRunner
from backend.prompts import SYSTEM_PROMPT, build_metrics_block
from preprocessing.normalization import conversation_from_payload
from preprocessing.pipeline import preprocess_conversation
from postprocesing.PostProceso import (
    EmotionMetrics as PPEmotionMetrics,
    HistoricalChunkMetrics,
    LLMResult,
    PostprocessDecision,
    PreprocessingMetrics as PPPreprocessingMetrics,
    process_llm_true_result,
)

logger = logging.getLogger("care.orchestrator")

SEVERITY_BAND_TO_ALERT_LEVEL = {
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}

RISK_TYPE_TITLES = {
    "bullying": "Acoso detectado",
    "grooming": "Manipulacion detectada",
    "distress": "Malestar emocional elevado",
}


async def analyze_chunk(
    *,
    pool: asyncpg.Pool,
    app: Any,
    conversation_id: str,
    chunk_id: int,
    child_user_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """Run the full analysis pipeline for a conversation chunk.

    Steps:
        1. Preprocessing  → chunk_metrics
        2. LLM analysis   → chunk_summaries + risk_assessments
        3. Postprocessing  → alerts + alert_recipients (if threshold met)
        4. Broadcast       → WebSocket + Web Push to guardian
    """
    try:
        # --- 1. Preprocessing ---
        metrics = await _run_preprocessing(pool, chunk_id, messages)

        # --- 2. LLM analysis ---
        llm_result, llm_raw = await _run_llm_analysis(pool, conversation_id, chunk_id, messages, metrics)

        # --- 3. Postprocessing decision ---
        decision = await _run_postprocessing(
            pool, child_user_id, conversation_id, chunk_id, metrics, llm_result,
        )

        # --- 4. Persist alert + broadcast ---
        await _handle_alert_decision(
            pool, app, child_user_id, conversation_id, chunk_id, decision, llm_result,
        )

        await pool.execute(
            "UPDATE conversation_chunks SET processing_status = 'processed' WHERE id = $1",
            chunk_id,
        )
        logger.info("Chunk %s processed successfully (decision=%s)", chunk_id, decision.postprocess_decision)

    except Exception:
        logger.exception("Failed to process chunk %s", chunk_id)
        with _suppress_db_errors():
            await pool.execute(
                "UPDATE conversation_chunks SET processing_status = 'failed' WHERE id = $1",
                chunk_id,
            )


# ---------------------------------------------------------------------------
# Step 1: Preprocessing
# ---------------------------------------------------------------------------

async def _run_preprocessing(
    pool: asyncpg.Pool,
    chunk_id: int,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    conversation_input = conversation_from_payload(messages)
    result = await asyncio.to_thread(preprocess_conversation, conversation_input)
    metrics = result.model_dump()

    await pool.execute(
        """
        INSERT INTO chunk_metrics (
            chunk_id, toxicity, insult_score, manipulation_similarity,
            targeting_intensity, dominance_ratio, activity_anomaly,
            distress_signal, confidence, risk_trend,
            emotion_anger, emotion_sadness, emotion_fear, pipeline_version
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
        ) ON CONFLICT (chunk_id) DO UPDATE SET
            toxicity = EXCLUDED.toxicity,
            insult_score = EXCLUDED.insult_score,
            manipulation_similarity = EXCLUDED.manipulation_similarity,
            targeting_intensity = EXCLUDED.targeting_intensity,
            dominance_ratio = EXCLUDED.dominance_ratio,
            activity_anomaly = EXCLUDED.activity_anomaly,
            distress_signal = EXCLUDED.distress_signal,
            confidence = EXCLUDED.confidence,
            risk_trend = EXCLUDED.risk_trend,
            emotion_anger = EXCLUDED.emotion_anger,
            emotion_sadness = EXCLUDED.emotion_sadness,
            emotion_fear = EXCLUDED.emotion_fear,
            pipeline_version = EXCLUDED.pipeline_version
        """,
        chunk_id,
        metrics["toxicity"],
        metrics["insult_score"],
        metrics["manipulation_similarity"],
        metrics["targeting_intensity"],
        metrics["dominance_ratio"],
        metrics["activity_anomaly"],
        metrics["distress_signal"],
        metrics["confidence"],
        metrics["risk_trend"],
        metrics["emotion"]["anger"],
        metrics["emotion"]["sadness"],
        metrics["emotion"]["fear"],
        "pipeline-v1",
    )
    logger.info("Chunk %s: preprocessing done (toxicity=%.2f, confidence=%.2f)", chunk_id, metrics["toxicity"], metrics["confidence"])
    return metrics


# ---------------------------------------------------------------------------
# Step 2: LLM Analysis
# ---------------------------------------------------------------------------

async def _run_llm_analysis(
    pool: asyncpg.Pool,
    conversation_id: str,
    chunk_id: int,
    messages: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> tuple[LLMResult, dict[str, Any]]:
    # Fetch historical summaries for context
    history_rows = await pool.fetch(
        """
        SELECT cs.summary_text, ra.rationale, ra.risk_type, ra.risk_level
        FROM conversation_chunks cc
        JOIN chunk_summaries cs ON cs.chunk_id = cc.id
        LEFT JOIN risk_assessments ra ON ra.chunk_id = cc.id
        WHERE cc.conversation_id = $1::uuid AND cc.id <> $2
        ORDER BY cc.chunk_end_at DESC
        LIMIT 5
        """,
        conversation_id,
        chunk_id,
    )
    history_text = ""
    if history_rows:
        parts = []
        for i, row in enumerate(history_rows, 1):
            entry = f"Report {i}: {row['summary_text']}"
            if row["risk_type"]:
                entry += f" (risk_type={row['risk_type']}, level={row['risk_level']})"
            parts.append(entry)
        history_text = "\n".join(parts)
    else:
        history_text = "No prior reports available for this user."

    # Build conversation text (anonymized)
    conversation_text = "\n".join(
        f"Speaker {msg['speaker']}: {msg['text']}" for msg in messages
    )

    metrics_block = build_metrics_block(metrics)
    prompt = SYSTEM_PROMPT + "\n\n" + f"""Conversation:

{conversation_text}

Metrics:
{metrics_block}

Historical reports:
{history_text}
"""

    runner = LLMRunner()
    raw_response = await runner.run(prompt)
    raw_text = raw_response.get("raw", "")

    # Parse JSON from LLM response
    llm_parsed = _parse_llm_json(raw_text)

    # Persist summary
    summary_text = llm_parsed.get("conversation_summary", raw_text[:500])
    await pool.execute(
        """
        INSERT INTO chunk_summaries (chunk_id, summary_text, model_name, prompt_version)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chunk_id) DO UPDATE SET
            summary_text = EXCLUDED.summary_text,
            model_name = EXCLUDED.model_name
        """,
        chunk_id,
        summary_text,
        "bedrock-claude-sonnet",
        "risk-monitor-v1",
    )

    # Persist risk assessment from LLM
    severity = llm_parsed.get("severity", "low")
    confidence = float(llm_parsed.get("confidence", 0.5))
    risk_types = llm_parsed.get("risk_types", {})
    dominant_risk = max(risk_types, key=risk_types.get) if risk_types else "none"
    risk_level_map = {"cyberbullying": "bullying", "grooming": "grooming", "self_harm": "distress"}
    db_risk_type = risk_level_map.get(dominant_risk, "none")

    if llm_parsed.get("risk_detected", False) and db_risk_type != "none":
        await pool.execute(
            """
            INSERT INTO risk_assessments (
                chunk_id, risk_type, risk_level, severity_score,
                confidence_score, rationale, model_name
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            chunk_id,
            db_risk_type,
            severity,
            float(risk_types.get(dominant_risk, 0.0)),
            confidence,
            llm_parsed.get("reasoning", ""),
            "bedrock-claude-sonnet",
        )

    llm_result = LLMResult(
        risk_detected=llm_parsed.get("risk_detected", False),
        risk_types=risk_types,
        severity=severity,
        confidence=confidence,
        key_evidence=llm_parsed.get("key_evidence", []),
        reasoning=llm_parsed.get("reasoning", ""),
        conversation_summary=summary_text,
    )

    logger.info(
        "Chunk %s: LLM done (risk_detected=%s, severity=%s)",
        chunk_id, llm_result.risk_detected, llm_result.severity,
    )
    return llm_result, llm_parsed


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response text, handling markdown code fences."""
    text = text.strip()
    if text.startswith("Error:"):
        logger.error("LLM request failed: %s", text[:300])
        return {
            "risk_detected": False,
            "risk_types": {"cyberbullying": 0.0, "grooming": 0.0, "self_harm": 0.0},
            "severity": "low",
            "confidence": 0.3,
            "key_evidence": [],
            "reasoning": text[:300],
            "conversation_summary": "LLM unavailable. Falling back to preprocessing-only safeguards.",
        }
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    logger.warning("Failed to parse LLM JSON: %.200s", text)
    return {
        "risk_detected": False,
        "risk_types": {"cyberbullying": 0.0, "grooming": 0.0, "self_harm": 0.0},
        "severity": "low",
        "confidence": 0.3,
        "key_evidence": [],
        "reasoning": text[:300],
        "conversation_summary": text[:300],
    }


# ---------------------------------------------------------------------------
# Step 3: Postprocessing
# ---------------------------------------------------------------------------

async def _run_postprocessing(
    pool: asyncpg.Pool,
    child_user_id: str,
    conversation_id: str,
    chunk_id: int,
    metrics: dict[str, Any],
    llm_result: LLMResult,
) -> PostprocessDecision:
    # Convert metrics dict to PostProceso dataclass
    emotion = metrics.get("emotion", {})
    pp_metrics = PPPreprocessingMetrics(
        toxicity=metrics["toxicity"],
        insult_score=metrics["insult_score"],
        emotion=PPEmotionMetrics(
            anger=emotion.get("anger", 0.0),
            sadness=emotion.get("sadness", 0.0),
            fear=emotion.get("fear", 0.0),
        ),
        manipulation_similarity=metrics["manipulation_similarity"],
        targeting_intensity=metrics["targeting_intensity"],
        dominance_ratio=metrics["dominance_ratio"],
        risk_trend=metrics["risk_trend"],
        activity_anomaly=metrics["activity_anomaly"],
        distress_signal=metrics["distress_signal"],
        confidence=metrics["confidence"],
    )

    # Fetch historical chunk metrics
    history_rows = await pool.fetch(
        """
        SELECT cc.id AS chunk_id, cc.conversation_id, cm.created_at,
               cm.toxicity, cm.insult_score, cm.manipulation_similarity,
               cm.targeting_intensity, cm.dominance_ratio, cm.activity_anomaly,
               cm.distress_signal, cm.confidence, cm.risk_trend,
               cm.emotion_anger, cm.emotion_sadness, cm.emotion_fear
        FROM conversation_chunks cc
        JOIN chunk_metrics cm ON cm.chunk_id = cc.id
        WHERE cc.conversation_id = $1::uuid AND cc.id <> $2
        ORDER BY cc.chunk_end_at DESC
        LIMIT 14
        """,
        conversation_id,
        chunk_id,
    )
    historical_metrics = [
        HistoricalChunkMetrics(
            chunk_id=str(row["chunk_id"]),
            conversation_id=str(row["conversation_id"]),
            created_at=row["created_at"],
            toxicity=float(row["toxicity"] or 0),
            insult_score=float(row["insult_score"] or 0),
            manipulation_similarity=float(row["manipulation_similarity"] or 0),
            targeting_intensity=float(row["targeting_intensity"] or 0),
            dominance_ratio=float(row["dominance_ratio"] or 0),
            activity_anomaly=float(row["activity_anomaly"] or 0),
            distress_signal=float(row["distress_signal"] or 0),
            confidence=float(row["confidence"] or 0),
            risk_trend=row["risk_trend"] or "stable",
            emotion_anger=float(row["emotion_anger"] or 0),
            emotion_sadness=float(row["emotion_sadness"] or 0),
            emotion_fear=float(row["emotion_fear"] or 0),
        )
        for row in history_rows
    ]

    # Fetch open alerts
    alert_rows = await pool.fetch(
        """
        SELECT id, child_user_id, conversation_id, chunk_id, risk_assessment_id,
               alert_type, alert_level, title, summary, status, created_at, updated_at
        FROM alerts
        WHERE child_user_id = $1::uuid
          AND conversation_id = $2::uuid
          AND status IN ('open', 'acknowledged')
        """,
        child_user_id,
        conversation_id,
    )
    existing_alerts = [dict(row) for row in alert_rows]
    # Convert uuid/datetime fields to strings for PostProceso compatibility
    for alert in existing_alerts:
        for key in ("id", "child_user_id", "conversation_id", "chunk_id", "risk_assessment_id"):
            if alert.get(key) is not None:
                alert[key] = str(alert[key])

    decision = process_llm_true_result(
        child_user_id=child_user_id,
        conversation_id=conversation_id,
        chunk_id=str(chunk_id),
        llm_result=llm_result,
        current_metrics=pp_metrics,
        historical_metrics=historical_metrics,
        existing_open_alerts=existing_alerts,
    )

    logger.info(
        "Chunk %s: postprocessing done (risk=%s, severity=%s, notify_guardian=%s)",
        chunk_id, decision.risk_type, decision.severity_band, decision.notify_guardian,
    )
    return decision


# ---------------------------------------------------------------------------
# Step 4: Alert persistence + broadcast
# ---------------------------------------------------------------------------

async def _handle_alert_decision(
    pool: asyncpg.Pool,
    app: Any,
    child_user_id: str,
    conversation_id: str,
    chunk_id: int,
    decision: PostprocessDecision,
    llm_result: LLMResult,
) -> None:
    risk_assessment_id = None

    # Persist risk assessment if validated
    if decision.risk_assessment_payload:
        ra = decision.risk_assessment_payload
        row = await pool.fetchrow(
            """
            INSERT INTO risk_assessments (
                chunk_id, risk_type, risk_level, severity_score,
                confidence_score, rationale, model_name
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            chunk_id,
            ra["risk_type"],
            ra["severity_band"],
            float(ra["severity_score"]) / 100.0,
            ra["confidence_score"],
            ra["rationale"],
            ra["model_name"],
        )
        if row:
            risk_assessment_id = row["id"]

    # Persist alert if needed
    alert_id = None
    if decision.alert_payload and (decision.create_new_alert or decision.update_existing_alert):
        ap = decision.alert_payload
        alert_level = SEVERITY_BAND_TO_ALERT_LEVEL.get(ap["severity_band"], "medium")
        title = RISK_TYPE_TITLES.get(ap["alert_type"], ap["alert_type"])

        if decision.create_new_alert:
            row = await pool.fetchrow(
                """
                INSERT INTO alerts (
                    child_user_id, conversation_id, chunk_id,
                    risk_assessment_id, alert_type, alert_level,
                    title, summary, status
                ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, 'open')
                RETURNING id
                """,
                child_user_id,
                conversation_id,
                chunk_id,
                risk_assessment_id,
                ap["alert_type"],
                alert_level,
                title,
                ap["summary"],
            )
            if row:
                alert_id = row["id"]
        elif decision.update_existing_alert and decision.alert_action_payload:
            target_id = decision.alert_action_payload.get("alert_id")
            if target_id:
                await pool.execute(
                    """
                    UPDATE alerts
                    SET alert_level = $2, summary = $3, chunk_id = $4,
                        risk_assessment_id = $5, updated_at = NOW()
                    WHERE id = $1::uuid
                    """,
                    target_id,
                    alert_level,
                    ap["summary"],
                    chunk_id,
                    risk_assessment_id,
                )
                alert_id = target_id

    # Link alert to guardian
    if alert_id and decision.notify_guardian:
        guardian_ids = await pool.fetch(
            """
            SELECT guardian_user_id FROM child_guardian_links
            WHERE child_user_id = $1::uuid
            """,
            child_user_id,
        )
        for row in guardian_ids:
            await pool.execute(
                """
                INSERT INTO alert_recipients (alert_id, user_id, recipient_role, delivered_at)
                VALUES ($1, $2, 'guardian', NOW())
                ON CONFLICT (alert_id, user_id) DO NOTHING
                """,
                alert_id if not isinstance(alert_id, str) else alert_id,
                row["guardian_user_id"],
            )

    # Broadcast to guardian(s) via WebSocket + Push
    if decision.notify_guardian or decision.create_new_alert or decision.update_existing_alert:
        await _broadcast_to_guardians(pool, app, child_user_id)


async def _broadcast_to_guardians(
    pool: asyncpg.Pool,
    app: Any,
    child_user_id: str,
) -> None:
    """Build fresh dashboard and broadcast to all connected guardians."""
    from api import AlertEnvelope, build_guardian_dashboard, send_web_push_notifications

    guardian_rows = await pool.fetch(
        "SELECT guardian_user_id FROM child_guardian_links WHERE child_user_id = $1::uuid",
        child_user_id,
    )
    hub = app.state.alert_hub

    for row in guardian_rows:
        guardian_id = str(row["guardian_user_id"])
        dashboard = await build_guardian_dashboard(pool, guardian_id)
        envelope = AlertEnvelope(type="alert_update", payload=dashboard)
        await hub.broadcast(envelope)
        await send_web_push_notifications(app, dashboard)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _suppress_db_errors:
    """Context manager that suppresses DB errors during cleanup."""
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, Exception):
            logger.warning("Suppressed error during cleanup: %s", exc_val)
            return True
        return False
