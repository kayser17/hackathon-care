import asyncio
import contextlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

import asyncpg
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pywebpush import WebPushException, webpush

from prompts import DEFAULT_PROMPT_METRICS
from backend.analysis_orchestrator import analyze_chunk

logger = logging.getLogger("care.api")

CHUNK_SIZE_MESSAGES = int(os.getenv("CHUNK_SIZE_MESSAGES", "4"))
CHUNK_WINDOW_SECONDS = int(os.getenv("CHUNK_WINDOW_SECONDS", "300"))


class PacienteCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    documento: str | None = Field(default=None, max_length=40)
    fecha_nacimiento: date | None = None


class PacienteOut(BaseModel):
    id: int
    nombre: str
    documento: str | None
    fecha_nacimiento: date | None
    creado_en: datetime


RiskLevel = Literal["high", "medium", "low"]


class AlertItem(BaseModel):
    id: str
    title: str
    detail: str
    level: RiskLevel


class MetricItem(BaseModel):
    label: str
    value: str
    helper: str


class TimelineEvent(BaseModel):
    id: str
    time: str
    title: str
    detail: str


class ParentDashboard(BaseModel):
    teenName: str
    updatedAt: str
    riskScore: int = Field(ge=0, le=100)
    riskLabel: str
    summary: str
    llmAnswer: str
    alerts: list[AlertItem]
    metrics: list[MetricItem]
    nextSteps: list[str]
    timeline: list[TimelineEvent]
    promptMetrics: dict[str, Any]


class AlertEnvelope(BaseModel):
    type: Literal["snapshot", "alert_update"]
    payload: ParentDashboard


class PushSubscriptionKeys(BaseModel):
    auth: str
    p256dh: str


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    expirationTime: int | None = None
    keys: PushSubscriptionKeys


class PushPublicKeyOut(BaseModel):
    publicKey: str


class SessionUserOut(BaseModel):
    id: str
    displayName: str
    role: Literal["guardian", "child"]
    email: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class ChildChatSendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class SessionCatalogOut(BaseModel):
    guardians: list[SessionUserOut]
    children: list[SessionUserOut]


class ChildChatParticipantOut(BaseModel):
    id: str
    displayName: str


class ChildChatMessageOut(BaseModel):
    id: str
    senderId: str
    senderName: str
    text: str
    sentAt: str


class ChildChatViewOut(BaseModel):
    conversationId: str
    title: str
    viewerUserId: str
    participants: list[ChildChatParticipantOut]
    messages: list[ChildChatMessageOut]


class MessageAccumulator:
    """Buffers chat messages per conversation until a chunk threshold is reached."""

    def __init__(self) -> None:
        self._buffers: dict[str, list[dict[str, Any]]] = {}
        self._first_ts: dict[str, datetime] = {}

    def append(self, conversation_id: str, message: dict[str, Any]) -> None:
        self._buffers.setdefault(conversation_id, []).append(message)
        if conversation_id not in self._first_ts:
            self._first_ts[conversation_id] = datetime.now(timezone.utc)

    def should_flush(self, conversation_id: str) -> bool:
        msgs = self._buffers.get(conversation_id, [])
        if len(msgs) >= CHUNK_SIZE_MESSAGES:
            return True
        first = self._first_ts.get(conversation_id)
        if first and (datetime.now(timezone.utc) - first).total_seconds() >= CHUNK_WINDOW_SECONDS:
            return len(msgs) > 0
        return False

    def flush(self, conversation_id: str) -> list[dict[str, Any]]:
        msgs = self._buffers.pop(conversation_id, [])
        self._first_ts.pop(conversation_id, None)
        return msgs

    def peek(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._buffers.get(conversation_id, []))

    def count(self, conversation_id: str) -> int:
        return len(self._buffers.get(conversation_id, []))


DEMO_CHAT_MESSAGES = [
    {"sender_key": "child_1", "text": "Nadie te quiere en nuestro grupo.", "sentAt": "17:34"},
    {"sender_key": "child_2", "text": "Para ya, no te he hecho nada.", "sentAt": "17:35"},
    {"sender_key": "child_1", "text": "Das pena, siempre molestas y caes fatal.", "sentAt": "17:36"},
    {"sender_key": "child_2", "text": "Me estas haciendo sentir fatal.", "sentAt": "17:37"},
    {"sender_key": "child_1", "text": "Pues vete, mejor si no apareces manana.", "sentAt": "17:38"},
    {"sender_key": "child_2", "text": "No quiero ir al cole por tu culpa.", "sentAt": "17:39"},
]

DEMO_CHILD_EMAILS = {
    "child_1": "diego.ramos@care.local",
    "child_2": "sofia.martinez@care.local",
}

SCHEMA_PATH = Path(__file__).resolve().with_name("init.sql")
if not SCHEMA_PATH.exists():
    SCHEMA_PATH = Path(__file__).resolve().parents[1] / "care-database" / "init.sql"


async def ensure_schema(pool: asyncpg.Pool) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.acquire() as connection:
        await connection.execute(schema_sql)


async def upsert_user(pool: asyncpg.Pool, display_name: str, email: str, password: str, role: str) -> asyncpg.Record:
    row = await pool.fetchrow(
        """
        UPDATE users
        SET display_name = $1, password = $3, role = $4, updated_at = NOW()
        WHERE LOWER(email) = LOWER($2)
        RETURNING id
        """,
        display_name,
        email,
        password,
        role,
    )
    if row is not None:
        return row

    return await pool.fetchrow(
        """
        INSERT INTO users (display_name, email, password, role)
        SELECT $1, $2, $3, $4
        WHERE NOT EXISTS (
            SELECT 1
            FROM users
            WHERE LOWER(email) = LOWER($2)
        )
        RETURNING id
        """,
        display_name,
        email,
        password,
        role,
    )


async def ensure_demo_data(pool: asyncpg.Pool) -> None:
    await pool.execute(
        """
        DELETE FROM users
        WHERE role IN ('guardian', 'child')
          AND LOWER(email) NOT IN (
              'laura.martinez@care.local',
              'diego.ramos@care.local',
              'sofia.martinez@care.local'
          )
        """
    )

    guardian = await upsert_user(pool, "Laura Martinez", "laura.martinez@care.local", "laura123", "guardian")
    child_1 = await upsert_user(pool, "Diego Ramos", "diego.ramos@care.local", "diego123", "child")
    child_2 = await upsert_user(pool, "Sofia Martinez", "sofia.martinez@care.local", "sofia123", "child")

    guardian_id = guardian["id"]
    child_1_id = child_1["id"]
    child_2_id = child_2["id"]

    await pool.execute(
        """
        UPDATE alerts
        SET title = 'Malestar emocional elevado', updated_at = NOW()
        WHERE title = 'Distress emocional elevado'
        """
    )

    await pool.execute(
        """
        INSERT INTO child_guardian_links (child_user_id, guardian_user_id, relationship_type)
        VALUES ($1, $2, 'parent')
        ON CONFLICT (child_user_id, guardian_user_id) DO NOTHING
        """,
        child_1_id,
        guardian_id,
    )

    await pool.execute(
        """
        INSERT INTO child_guardian_links (child_user_id, guardian_user_id, relationship_type)
        VALUES ($1, $2, 'parent')
        ON CONFLICT (child_user_id, guardian_user_id) DO NOTHING
        """,
        child_2_id,
        guardian_id,
    )

    conversation = await pool.fetchrow(
        """
        SELECT c.id
        FROM conversations c
        JOIN conversation_participants cp1 ON cp1.conversation_id = c.id AND cp1.user_id = $1
        JOIN conversation_participants cp2 ON cp2.conversation_id = c.id AND cp2.user_id = $2
        WHERE c.conversation_type = 'direct'
        LIMIT 1
        """,
        child_1_id,
        child_2_id,
    )

    if conversation is None:
        conversation = await pool.fetchrow(
            """
            INSERT INTO conversations (conversation_type, status)
            VALUES ('direct', 'active')
            RETURNING id
            """
        )
        conversation_id = conversation["id"]
        await pool.execute(
            """
            INSERT INTO conversation_participants (conversation_id, user_id)
            VALUES ($1, $2), ($1, $3)
            ON CONFLICT (conversation_id, user_id) DO NOTHING
            """,
            conversation_id,
            child_1_id,
            child_2_id,
        )
    else:
        conversation_id = conversation["id"]
        await pool.execute(
            """
            INSERT INTO conversation_participants (conversation_id, user_id)
            VALUES ($1, $2), ($1, $3)
            ON CONFLICT (conversation_id, user_id) DO NOTHING
            """,
            conversation_id,
            child_1_id,
            child_2_id,
        )

    existing_alert = await pool.fetchval(
        """
        SELECT a.id
        FROM alerts a
        WHERE a.child_user_id = $1
        LIMIT 1
        """,
        child_2_id,
    )
    if existing_alert is not None:
        return

    chunk = await pool.fetchrow(
        """
        INSERT INTO conversation_chunks (
            conversation_id,
            chunk_start_at,
            chunk_end_at,
            message_count,
            processing_status
        )
        VALUES (
            $1,
            NOW() - INTERVAL '18 minutes',
            NOW() - INTERVAL '4 minutes',
            16,
            'processed'
        )
        RETURNING id
        """,
        conversation_id,
    )
    chunk_id = chunk["id"]

    await pool.execute(
        """
        INSERT INTO chunk_metrics (
            chunk_id,
            toxicity,
            insult_score,
            manipulation_similarity,
            targeting_intensity,
            dominance_ratio,
            activity_anomaly,
            distress_signal,
            confidence,
            risk_trend,
            emotion_anger,
            emotion_sadness,
            emotion_fear,
            pipeline_version
        )
        VALUES (
            $1,
            0.6800,
            0.7200,
            0.8100,
            0.8500,
            0.9000,
            0.6000,
            0.5500,
            0.7800,
            'increasing',
            0.6000,
            0.5000,
            0.3000,
            'demo-v1'
        )
        ON CONFLICT (chunk_id) DO NOTHING
        """,
        chunk_id,
    )

    await pool.execute(
        """
        INSERT INTO chunk_summaries (chunk_id, summary_text, model_name, prompt_version)
        VALUES (
            $1,
            'Se observan expresiones de rechazo social, retirada del grupo y aumento del malestar emocional en el periodo reciente.',
            'gpt-4o-mini',
            'risk-monitor-v1'
        )
        ON CONFLICT (chunk_id) DO NOTHING
        """,
        chunk_id,
    )

    assessment = await pool.fetchrow(
        """
        INSERT INTO risk_assessments (
            chunk_id,
            risk_type,
            risk_level,
            severity_score,
            confidence_score,
            rationale,
            model_name
        )
        VALUES (
            $1,
            'bullying',
            'high',
            0.7800,
            0.7800,
            'Alta intensidad de insulto, focalizacion repetida y tono de tristeza creciente.',
            'gpt-4o-mini'
        )
        RETURNING id
        """,
        chunk_id,
    )
    assessment_id = assessment["id"]

    alert = await pool.fetchrow(
        """
        INSERT INTO alerts (
            child_user_id,
            conversation_id,
            chunk_id,
            risk_assessment_id,
            alert_type,
            alert_level,
            title,
            summary,
            status
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            'bullying',
            'critical',
            'Malestar emocional elevado',
            'Se detecta un patron compatible con acoso relacional y aumento del malestar emocional.',
            'open'
        )
        RETURNING id
        """,
        child_2_id,
        conversation_id,
        chunk_id,
        assessment_id,
    )

    await pool.execute(
        """
        INSERT INTO alert_recipients (alert_id, user_id, recipient_role, delivered_at)
        VALUES ($1, $2, 'guardian', NOW())
        ON CONFLICT (alert_id, user_id) DO NOTHING
        """,
        alert["id"],
        guardian_id,
    )


def build_default_dashboard() -> ParentDashboard:
    return ParentDashboard(
        teenName="",
        updatedAt="—",
        riskScore=0,
        riskLabel="Sin datos",
        summary="Aun no se han procesado conversaciones. Los resultados apareceran aqui cuando haya actividad.",
        llmAnswer="",
        alerts=[],
        metrics=[
            MetricItem(label="Bienestar emocional", value="Sin datos", helper="Se actualizara con la primera conversacion"),
            MetricItem(label="Interaccion social", value="Sin datos", helper="Se actualizara con la primera conversacion"),
            MetricItem(label="Nivel de seguimiento", value="Sin datos", helper="Se actualizara con la primera conversacion"),
            MetricItem(label="Estado del caso", value="Sin datos", helper="Se actualizara con la primera conversacion"),
        ],
        nextSteps=[],
        timeline=[],
        promptMetrics={},
    )


def alert_level_to_risk(level: str) -> tuple[int, str]:
    if level == "critical":
        return 92, "Alerta critica"
    if level == "high":
        return 78, "Alerta prioritaria"
    return 54, "Seguimiento recomendado"


def assessment_level_to_ui(level: str | None) -> RiskLevel:
    if level == "high":
        return "high"
    if level == "medium":
        return "medium"
    return "low"


def alert_type_label(alert_type: str) -> str:
    mapping = {
        "bullying": "Acoso detectado",
        "grooming": "Manipulacion detectada",
        "distress": "Malestar emocional",
    }
    return mapping.get(alert_type, alert_type)


async def build_guardian_dashboard(pool: asyncpg.Pool, guardian_user_id: str) -> ParentDashboard:
    overview = await pool.fetchrow(
        """
        SELECT
            child_u.id AS child_user_id,
            child_u.display_name AS child_name,
            a.id AS alert_id,
            a.alert_level,
            a.alert_type,
            a.title,
            a.summary,
            a.created_at AS alert_created_at,
            a.updated_at AS alert_updated_at,
            rs.risk_level,
            rs.risk_type,
            rs.severity_score,
            rs.confidence_score,
            rs.rationale,
            cs.summary_text,
            cm.toxicity,
            cm.insult_score,
            cm.manipulation_similarity,
            cm.targeting_intensity,
            cm.dominance_ratio,
            cm.activity_anomaly,
            cm.distress_signal,
            cm.confidence,
            cm.risk_trend,
            cm.emotion_anger,
            cm.emotion_sadness,
            cm.emotion_fear
        FROM child_guardian_links cgl
        JOIN users child_u ON child_u.id = cgl.child_user_id
        LEFT JOIN alerts a ON a.child_user_id = child_u.id
        LEFT JOIN risk_assessments rs ON rs.id = a.risk_assessment_id
        LEFT JOIN chunk_metrics cm ON cm.chunk_id = a.chunk_id
        LEFT JOIN chunk_summaries cs ON cs.chunk_id = a.chunk_id
        WHERE cgl.guardian_user_id = $1::uuid
        ORDER BY a.created_at DESC NULLS LAST, child_u.created_at ASC
        LIMIT 1
        """,
        guardian_user_id,
    )

    if overview is None:
        return build_default_dashboard()

    if overview["alert_id"] is None:
        fallback = build_default_dashboard()
        return fallback.model_copy(update={"teenName": overview["child_name"]})

    metrics_payload = {
        "toxicity": float(overview["toxicity"] or 0),
        "insult_score": float(overview["insult_score"] or 0),
        "emotion": {
            "anger": float(overview["emotion_anger"] or 0),
            "sadness": float(overview["emotion_sadness"] or 0),
            "fear": float(overview["emotion_fear"] or 0),
        },
        "manipulation_similarity": float(overview["manipulation_similarity"] or 0),
        "targeting_intensity": float(overview["targeting_intensity"] or 0),
        "dominance_ratio": float(overview["dominance_ratio"] or 0),
        "risk_trend": overview["risk_trend"] or "stable",
        "activity_anomaly": float(overview["activity_anomaly"] or 0),
        "distress_signal": float(overview["distress_signal"] or 0),
        "confidence": float(overview["confidence"] or overview["confidence_score"] or 0),
    }
    risk_score, risk_label = alert_level_to_risk(overview["alert_level"])

    alert_rows = await pool.fetch(
        """
        SELECT
            a.id,
            a.title,
            a.summary,
            a.alert_level,
            a.alert_type,
            rs.risk_level
        FROM alerts a
        LEFT JOIN risk_assessments rs ON rs.id = a.risk_assessment_id
        WHERE a.child_user_id = $1::uuid
        ORDER BY a.created_at DESC
        LIMIT 3
        """,
        overview["child_user_id"],
    )

    timeline_rows = await pool.fetch(
        """
        SELECT
            a.id AS alert_id,
            a.created_at,
            a.title,
            cs.summary_text,
            rs.rationale
        FROM alerts a
        LEFT JOIN chunk_summaries cs ON cs.chunk_id = a.chunk_id
        LEFT JOIN risk_assessments rs ON rs.id = a.risk_assessment_id
        WHERE a.child_user_id = $1::uuid
        ORDER BY a.created_at DESC
        LIMIT 3
        """,
        overview["child_user_id"],
    )

    next_steps = [
        "Revisar el resumen del ultimo chunk y confirmar si el patron sigue activo.",
        "Hablar con el menor en un entorno privado y sin confrontacion.",
        "Escalar a orientacion o apoyo profesional si aumenta la frecuencia o gravedad.",
    ]

    return ParentDashboard(
        teenName=overview["child_name"],
        updatedAt=overview["alert_updated_at"].strftime("%d/%m %H:%M"),
        riskScore=risk_score,
        riskLabel=risk_label,
        summary=overview["summary"],
        llmAnswer=overview["summary_text"] or overview["rationale"] or overview["summary"],
        alerts=[
            AlertItem(
                id=str(row["id"]),
                title=row["title"],
                detail=row["summary"],
                level=assessment_level_to_ui(row["risk_level"] or ("high" if row["alert_level"] == "critical" else "medium")),
            )
            for row in alert_rows
        ],
        metrics=[
            MetricItem(label="Bienestar emocional", value="Requiere atencion", helper="Se observan senales de malestar reciente"),
            MetricItem(label="Interaccion social", value="Cambios detectados", helper="Puede haber aislamiento o conflicto relacional"),
            MetricItem(label="Nivel de seguimiento", value="Alto", helper="Se recomienda observacion cercana"),
            MetricItem(label="Estado del caso", value="En revision", helper="Se actualizara si hay cambios relevantes"),
        ],
        nextSteps=next_steps,
        timeline=[
            TimelineEvent(
                id=f"timeline-{index}",
                time=row["created_at"].strftime("%H:%M"),
                title=row["title"],
                detail=row["summary_text"] or row["rationale"] or "Evento de riesgo registrado",
            )
            for index, row in enumerate(timeline_rows, start=1)
        ],
        promptMetrics=metrics_payload,
    )


async def seed_child_chat_messages(pool: asyncpg.Pool) -> list[ChildChatMessageOut]:
    rows = await pool.fetch(
        """
        SELECT id, display_name, LOWER(email) AS email
        FROM users
        WHERE LOWER(email) = ANY($1::text[])
        """,
        list(DEMO_CHILD_EMAILS.values()),
    )
    users_by_email = {row["email"]: row for row in rows}

    messages: list[ChildChatMessageOut] = []
    for index, item in enumerate(DEMO_CHAT_MESSAGES, start=1):
        sender = users_by_email[DEMO_CHILD_EMAILS[item["sender_key"]]]
        messages.append(
            ChildChatMessageOut(
                id=f"msg-{index}",
                senderId=str(sender["id"]),
                senderName=sender["display_name"],
                text=item["text"],
                sentAt=item["sentAt"],
            )
        )
    return messages


async def get_shared_child_chat_messages(pool: asyncpg.Pool, conversation_id: str) -> list[ChildChatMessageOut]:
    messages_by_conversation: dict[str, list[ChildChatMessageOut]] = app.state.child_chat_messages
    if conversation_id not in messages_by_conversation:
        messages_by_conversation[conversation_id] = []
    return messages_by_conversation[conversation_id]


class AlertHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.lock:
            self.connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.discard(websocket)

    async def broadcast(self, message: AlertEnvelope) -> None:
        payload = json.dumps(message.model_dump())
        async with self.lock:
            sockets = list(self.connections)

        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_text(payload)
            except RuntimeError:
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(websocket)


async def save_push_subscription(pool: asyncpg.Pool, subscription: PushSubscriptionPayload) -> None:
    await pool.execute(
        """
        INSERT INTO push_subscriptions (endpoint, subscription, actualizado_en)
        VALUES ($1, $2::jsonb, NOW())
        ON CONFLICT (endpoint)
        DO UPDATE SET subscription = EXCLUDED.subscription, actualizado_en = NOW()
        """,
        subscription.endpoint,
        json.dumps(subscription.model_dump()),
    )


async def delete_push_subscription(pool: asyncpg.Pool, endpoint: str) -> None:
    await pool.execute("DELETE FROM push_subscriptions WHERE endpoint = $1", endpoint)


def build_push_message(payload: ParentDashboard) -> dict[str, Any]:
    top_alert = payload.alerts[0] if payload.alerts else None
    body = (
        f"{top_alert.title}. {top_alert.detail}"
        if top_alert
        else "Hay una nueva actualizacion de seguimiento."
    )
    return {
        "title": f"Actualizacion sobre {payload.teenName}",
        "body": body,
        "url": "/",
        "tag": f"care-risk-{payload.teenName}",
    }


async def send_web_push_notifications(app: FastAPI, payload: ParentDashboard) -> None:
    if not app.state.push_enabled:
        return

    pool: asyncpg.Pool = app.state.pool
    rows = await pool.fetch("SELECT endpoint, subscription FROM push_subscriptions")
    if not rows:
        return

    message = json.dumps(build_push_message(payload))
    vapid_private_key = app.state.vapid_private_key
    vapid_claims = {"sub": app.state.vapid_subject}

    stale_endpoints: list[str] = []
    for row in rows:
        try:
            webpush(
                subscription_info=row["subscription"],
                data=message,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {404, 410}:
                stale_endpoints.append(row["endpoint"])
            else:
                print(f"Error enviando push a {row['endpoint']}: {exc}")

    for endpoint in stale_endpoints:
        await delete_push_subscription(pool, endpoint)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no esta configurada")

    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    app.state.pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    await ensure_schema(app.state.pool)
    if os.getenv("CARE_SEED_DEMO", "false").lower() in ("1", "true", "yes"):
        await ensure_demo_data(app.state.pool)
        logger.info("Demo seed data loaded (CARE_SEED_DEMO=true)")
    else:
        logger.info("Demo seed skipped (CARE_SEED_DEMO!=true). Set CARE_SEED_DEMO=true to enable.")
    app.state.alert_hub = AlertHub()
    app.state.alert_state = build_default_dashboard()
    app.state.child_chat_messages = {}
    app.state.message_accumulator = MessageAccumulator()
    app.state.vapid_public_key = os.getenv("CARE_WEB_PUSH_PUBLIC_KEY")
    app.state.vapid_private_key = os.getenv("CARE_WEB_PUSH_PRIVATE_KEY")
    app.state.vapid_subject = os.getenv("CARE_WEB_PUSH_SUBJECT", "mailto:care@example.com")
    app.state.push_enabled = bool(app.state.vapid_public_key and app.state.vapid_private_key)

    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(title="Care Backend", version="0.3.0", lifespan=lifespan)

allowed_origins = os.getenv("CARE_ALLOWED_ORIGINS", "http://localhost:13000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _create_chunk_and_analyze(
    conversation_id: str,
    child_user_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """Create a conversation_chunks row and spawn background analysis."""
    pool: asyncpg.Pool = app.state.pool
    now = datetime.now(timezone.utc)
    timestamps = [msg.get("timestamp", now.isoformat()) for msg in messages]
    try:
        earliest = min(datetime.fromisoformat(t) if isinstance(t, str) else t for t in timestamps)
    except (ValueError, TypeError):
        earliest = now

    chunk = await pool.fetchrow(
        """
        INSERT INTO conversation_chunks (
            conversation_id, chunk_start_at, chunk_end_at,
            message_count, processing_status
        ) VALUES ($1::uuid, $2, $3, $4, 'pending')
        RETURNING id
        """,
        conversation_id,
        earliest,
        now,
        len(messages),
    )
    chunk_id = chunk["id"]
    logger.info(
        "Created chunk %s for conversation %s (%d messages)",
        chunk_id, conversation_id, len(messages),
    )

    asyncio.create_task(
        analyze_chunk(
            pool=pool,
            app=app,
            conversation_id=conversation_id,
            chunk_id=chunk_id,
            child_user_id=child_user_id,
            messages=messages,
        )
    )


@app.get("/health")
async def health() -> dict[str, str]:
    pool = app.state.pool
    await pool.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/api/pacientes", response_model=list[PacienteOut])
async def listar_pacientes() -> list[dict[str, Any]]:
    pool = app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, nombre, documento, fecha_nacimiento, creado_en
        FROM pacientes
        ORDER BY id DESC
        """
    )
    return [dict(row) for row in rows]


@app.post("/api/pacientes", response_model=PacienteOut, status_code=201)
async def crear_paciente(payload: PacienteCreate) -> dict[str, Any]:
    pool = app.state.pool
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO pacientes (nombre, documento, fecha_nacimiento)
            VALUES ($1, $2, $3)
            RETURNING id, nombre, documento, fecha_nacimiento, creado_en
            """,
            payload.nombre,
            payload.documento,
            payload.fecha_nacimiento,
        )
    except asyncpg.exceptions.UniqueViolationError as exc:
        raise HTTPException(status_code=409, detail="El documento ya existe") from exc

    if row is None:
        raise HTTPException(status_code=500, detail="No se pudo crear el paciente")

    return dict(row)


@app.get("/api/alerts/state", response_model=ParentDashboard)
async def get_alert_state() -> ParentDashboard:
    pool = app.state.pool
    guardian_id = await pool.fetchval(
        """
        SELECT id
        FROM users
        WHERE role = 'guardian' AND is_active = TRUE
        ORDER BY created_at ASC
        LIMIT 1
        """
    )
    if guardian_id is None:
        return build_default_dashboard()
    return await build_guardian_dashboard(pool, str(guardian_id))


@app.get("/api/session/guardian/{user_id}/dashboard", response_model=ParentDashboard)
async def get_guardian_dashboard(user_id: str) -> ParentDashboard:
    return await build_guardian_dashboard(app.state.pool, user_id)


@app.get("/api/session/catalog", response_model=SessionCatalogOut)
async def get_session_catalog() -> SessionCatalogOut:
    pool = app.state.pool
    guardians_rows = await pool.fetch(
        """
        SELECT id, display_name, email
        FROM users
        WHERE role = 'guardian' AND is_active = TRUE
        ORDER BY display_name ASC
        """
    )
    children_rows = await pool.fetch(
        """
        SELECT id, display_name, email
        FROM users
        WHERE role = 'child' AND is_active = TRUE
        ORDER BY display_name ASC
        """
    )

    return SessionCatalogOut(
        guardians=[
            SessionUserOut(
                id=str(row["id"]),
                displayName=row["display_name"],
                email=row["email"],
                role="guardian",
            )
            for row in guardians_rows
        ],
        children=[
            SessionUserOut(
                id=str(row["id"]),
                displayName=row["display_name"],
                email=row["email"],
                role="child",
            )
            for row in children_rows
        ],
    )


@app.post("/api/session/login", response_model=SessionUserOut)
async def login(payload: LoginRequest) -> SessionUserOut:
    row = await app.state.pool.fetchrow(
        """
        SELECT id, display_name, email, role
        FROM users
        WHERE LOWER(email) = LOWER($1)
          AND password = $2
          AND role IN ('guardian', 'child')
          AND is_active = TRUE
        LIMIT 1
        """,
        payload.email.strip(),
        payload.password,
    )

    if row is None:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    role = "guardian" if row["role"] == "guardian" else "child"
    return SessionUserOut(
        id=str(row["id"]),
        displayName=row["display_name"],
        email=row["email"],
        role=role,
    )


@app.get("/api/session/child/{user_id}/chat", response_model=ChildChatViewOut)
async def get_child_chat_view(user_id: str) -> ChildChatViewOut:
    pool = app.state.pool
    conversation = await pool.fetchrow(
        """
        SELECT
            c.id AS conversation_id,
            other_u.id AS other_user_id,
            other_u.display_name AS other_display_name,
            viewer_u.display_name AS viewer_display_name
        FROM users viewer_u
        JOIN conversation_participants viewer_cp ON viewer_cp.user_id = viewer_u.id
        JOIN conversations c ON c.id = viewer_cp.conversation_id AND c.status = 'active'
        JOIN conversation_participants other_cp ON other_cp.conversation_id = c.id AND other_cp.user_id <> viewer_u.id
        JOIN users other_u ON other_u.id = other_cp.user_id
        WHERE viewer_u.id = $1::uuid
          AND viewer_u.role = 'child'
        ORDER BY c.updated_at DESC
        LIMIT 1
        """,
        user_id,
    )

    if conversation is None:
        raise HTTPException(status_code=404, detail="No se encontro conversacion activa para este menor")

    viewer_id = user_id
    other_id = str(conversation["other_user_id"])
    participants = [
        ChildChatParticipantOut(id=viewer_id, displayName=conversation["viewer_display_name"]),
        ChildChatParticipantOut(id=other_id, displayName=conversation["other_display_name"]),
    ]
    messages = await get_shared_child_chat_messages(pool, str(conversation["conversation_id"]))

    return ChildChatViewOut(
        conversationId=str(conversation["conversation_id"]),
        title=conversation["other_display_name"],
        viewerUserId=viewer_id,
        participants=participants,
        messages=messages,
    )


@app.post("/api/session/child/{user_id}/chat/messages", response_model=ChildChatViewOut)
async def send_child_chat_message(user_id: str, payload: ChildChatSendRequest) -> ChildChatViewOut:
    pool = app.state.pool
    conversation_id = await pool.fetchval(
        """
        SELECT c.id
        FROM users viewer_u
        JOIN conversation_participants viewer_cp ON viewer_cp.user_id = viewer_u.id
        JOIN conversations c ON c.id = viewer_cp.conversation_id AND c.status = 'active'
        WHERE viewer_u.id = $1::uuid
          AND viewer_u.role = 'child'
        ORDER BY c.updated_at DESC
        LIMIT 1
        """,
        user_id,
    )
    sender = await pool.fetchrow(
        """
        SELECT id, display_name
        FROM users
        WHERE id = $1::uuid
          AND role = 'child'
          AND is_active = TRUE
        """,
        user_id,
    )

    if conversation_id is None or sender is None:
        raise HTTPException(status_code=404, detail="No se encontro conversacion activa para este menor")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacio")

    messages = await get_shared_child_chat_messages(pool, str(conversation_id))
    messages.append(
        ChildChatMessageOut(
            id=f"msg-{len(messages) + 1}",
            senderId=str(sender["id"]),
            senderName=sender["display_name"],
            text=text,
            sentAt=datetime.now().strftime("%H:%M"),
        )
    )

    # Feed message into the accumulator for pipeline analysis
    accumulator: MessageAccumulator = app.state.message_accumulator
    conv_id_str = str(conversation_id)
    accumulator.append(conv_id_str, {
        "speaker": sender["display_name"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
    })

    if accumulator.should_flush(conv_id_str):
        buffered = accumulator.flush(conv_id_str)
        # Resolve child_user_id: the child who is the target of monitoring
        # (the "other" participant, or the sender themselves — use all linked children)
        child_user_ids = await pool.fetch(
            """
            SELECT cp.user_id
            FROM conversation_participants cp
            JOIN users u ON u.id = cp.user_id AND u.role = 'child'
            WHERE cp.conversation_id = $1::uuid
            """,
            conv_id_str,
        )
        # Trigger analysis for each child in the conversation
        for child_row in child_user_ids:
            await _create_chunk_and_analyze(
                conversation_id=conv_id_str,
                child_user_id=str(child_row["user_id"]),
                messages=buffered,
            )

    return await get_child_chat_view(user_id)


@app.post("/api/alerts/publish", response_model=AlertEnvelope)
async def publish_alert_state(payload: ParentDashboard) -> AlertEnvelope:
    app.state.alert_state = payload
    message = AlertEnvelope(type="alert_update", payload=payload)
    await app.state.alert_hub.broadcast(message)
    await send_web_push_notifications(app, payload)
    return message


@app.post("/api/analysis/trigger/{conversation_id}")
async def trigger_analysis(conversation_id: str) -> dict[str, Any]:
    """Manually trigger analysis on accumulated messages (or all chat messages) for a conversation."""
    pool: asyncpg.Pool = app.state.pool
    accumulator: MessageAccumulator = app.state.message_accumulator

    # First try accumulated buffer
    buffered = accumulator.flush(conversation_id)

    # If no buffered messages, use the in-memory chat messages as fallback
    if not buffered:
        chat_messages = app.state.child_chat_messages.get(conversation_id, [])
        if not chat_messages:
            raise HTTPException(status_code=404, detail="No hay mensajes acumulados para esta conversacion")
        buffered = [
            {
                "speaker": msg.senderName,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": msg.text,
            }
            for msg in chat_messages
        ]

    child_user_ids = await pool.fetch(
        """
        SELECT cp.user_id
        FROM conversation_participants cp
        JOIN users u ON u.id = cp.user_id AND u.role = 'child'
        WHERE cp.conversation_id = $1::uuid
        """,
        conversation_id,
    )
    if not child_user_ids:
        raise HTTPException(status_code=404, detail="No se encontraron menores en esta conversacion")

    triggered = []
    for child_row in child_user_ids:
        await _create_chunk_and_analyze(
            conversation_id=conversation_id,
            child_user_id=str(child_row["user_id"]),
            messages=buffered,
        )
        triggered.append(str(child_row["user_id"]))

    return {
        "status": "analysis_triggered",
        "conversation_id": conversation_id,
        "message_count": len(buffered),
        "children_analyzed": triggered,
    }


@app.get("/api/push/public-key", response_model=PushPublicKeyOut)
async def get_push_public_key() -> PushPublicKeyOut:
    if not app.state.push_enabled:
        raise HTTPException(status_code=503, detail="Web Push no esta configurado en el backend")
    return PushPublicKeyOut(publicKey=app.state.vapid_public_key)


@app.post("/api/push/subscribe", status_code=201)
async def subscribe_push(payload: PushSubscriptionPayload) -> dict[str, str]:
    if not app.state.push_enabled:
        raise HTTPException(status_code=503, detail="Web Push no esta configurado en el backend")
    await save_push_subscription(app.state.pool, payload)
    return {"status": "subscribed"}


@app.delete("/api/push/subscribe", status_code=204)
async def unsubscribe_push(payload: PushSubscriptionPayload) -> Response:
    if not app.state.push_enabled:
        raise HTTPException(status_code=503, detail="Web Push no esta configurado en el backend")
    await delete_push_subscription(app.state.pool, payload.endpoint)
    return Response(status_code=204)


@app.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket) -> None:
    hub: AlertHub = app.state.alert_hub
    await hub.connect(websocket)

    try:
        guardian_id = await app.state.pool.fetchval(
            """
            SELECT id
            FROM users
            WHERE role = 'guardian' AND is_active = TRUE
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        payload = (
            await build_guardian_dashboard(app.state.pool, str(guardian_id))
            if guardian_id is not None
            else build_default_dashboard()
        )
        snapshot = AlertEnvelope(type="snapshot", payload=payload)
        await websocket.send_text(json.dumps(snapshot.model_dump()))

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(RuntimeError):
            await hub.disconnect(websocket)
