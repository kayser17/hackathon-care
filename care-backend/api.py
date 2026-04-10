import asyncio
import contextlib
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import asyncpg
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pywebpush import WebPushException, webpush

from prompts import DEFAULT_PROMPT_METRICS


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
    trend: str


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


DEMO_CHAT_MESSAGES = [
    {"sender_key": "child_sofia", "text": "Hola, estas por ahi?", "sentAt": "17:34"},
    {"sender_key": "child_mateo", "text": "Si. Hoy no queria volver al grupo.", "sentAt": "17:35"},
    {"sender_key": "child_sofia", "text": "Otra vez se pusieron pesados contigo?", "sentAt": "17:36"},
    {"sender_key": "child_mateo", "text": "Si, empezaron con bromas y luego ya no paro.", "sentAt": "17:37"},
    {"sender_key": "child_sofia", "text": "Si quieres salimos del chat y hablas conmigo por aqui.", "sentAt": "17:38"},
    {"sender_key": "child_mateo", "text": "Gracias. Estoy un poco agobiado, la verdad.", "sentAt": "17:39"},
]

SCHEMA_PATH = Path(__file__).resolve().with_name("init.sql")


async def ensure_schema(pool: asyncpg.Pool) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.acquire() as connection:
        await connection.execute(schema_sql)


async def upsert_user(pool: asyncpg.Pool, display_name: str, email: str, role: str) -> asyncpg.Record:
    row = await pool.fetchrow(
        """
        UPDATE users
        SET display_name = $1, role = $3, updated_at = NOW()
        WHERE LOWER(email) = LOWER($2)
        RETURNING id
        """,
        display_name,
        email,
        role,
    )
    if row is not None:
        return row

    return await pool.fetchrow(
        """
        INSERT INTO users (display_name, email, role)
        SELECT $1, $2, $3
        WHERE NOT EXISTS (
            SELECT 1
            FROM users
            WHERE LOWER(email) = LOWER($2)
        )
        RETURNING id
        """,
        display_name,
        email,
        role,
    )


async def ensure_demo_data(pool: asyncpg.Pool) -> None:
    guardian = await upsert_user(pool, "Laura Martinez", "laura.guardian@care.local", "guardian")
    child_sofia = await upsert_user(pool, "Sofia", "sofia.child@care.local", "child")
    child_mateo = await upsert_user(pool, "Mateo", "mateo.child@care.local", "child")

    guardian_id = guardian["id"]
    child_sofia_id = child_sofia["id"]
    child_mateo_id = child_mateo["id"]

    await pool.execute(
        """
        INSERT INTO child_guardian_links (child_user_id, guardian_user_id, relationship_type)
        VALUES ($1, $2, 'mother')
        ON CONFLICT (child_user_id, guardian_user_id) DO NOTHING
        """,
        child_sofia_id,
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
        child_sofia_id,
        child_mateo_id,
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
            child_sofia_id,
            child_mateo_id,
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
            child_sofia_id,
            child_mateo_id,
        )

    existing_alert = await pool.fetchval(
        """
        SELECT a.id
        FROM alerts a
        WHERE a.child_user_id = $1
        LIMIT 1
        """,
        child_sofia_id,
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
            'Distress emocional elevado',
            'Se detecta un patron compatible con acoso relacional y aumento del malestar emocional.',
            'open'
        )
        RETURNING id
        """,
        child_sofia_id,
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
    prompt_metrics = DEFAULT_PROMPT_METRICS.copy()
    return ParentDashboard(
        teenName="Sofia",
        updatedAt="Hoy, 09:12",
        riskScore=78,
        riskLabel="Alerta prioritaria",
        summary=(
            "El sistema detecta senales consistentes con aislamiento social, tristeza "
            "sostenida y comentarios de rechazo en un chat reciente."
        ),
        llmAnswer=(
            "El analisis del LLM sugiere un riesgo emocional creciente. Se observan "
            "expresiones de desesperanza, retirada del grupo y una interaccion repetida "
            "donde la menor recibe mensajes descalificadores. La recomendacion es iniciar "
            "una conversacion calmada hoy mismo, validar como se siente y valorar contacto "
            "con orientacion escolar o apoyo clinico si el patron persiste."
        ),
        alerts=[
            AlertItem(
                id="a1",
                title="Distress emocional elevado",
                detail="Lenguaje con tristeza, agotamiento y sensacion de exclusion en las ultimas 24 horas.",
                level="high",
            ),
            AlertItem(
                id="a2",
                title="Posible acoso relacional",
                detail="Mensajes con rechazo repetido y foco sostenido sobre la menor en un mismo grupo.",
                level="high",
            ),
            AlertItem(
                id="a3",
                title="Cambio de actividad",
                detail="Menor participacion y respuestas mas cortas respecto a su patron habitual.",
                level="medium",
            ),
        ],
        metrics=[
            MetricItem(label="Toxicidad", value=f"{prompt_metrics['toxicity']:.2f}", trend="senal de hostilidad"),
            MetricItem(label="Insulto", value=f"{prompt_metrics['insult_score']:.2f}", trend="agresion verbal"),
            MetricItem(label="Distress", value=f"{prompt_metrics['distress_signal']:.2f}", trend="malestar detectado"),
            MetricItem(label="Confianza", value=f"{prompt_metrics['confidence']:.2f}", trend="fiabilidad del analisis"),
        ],
        nextSteps=[
            "Hablar con Sofia hoy en un entorno privado y sin confrontacion.",
            "Preguntar por su experiencia escolar y su relacion con el grupo del chat.",
            "Registrar cambios de sueno, apetito o aislamiento durante esta semana.",
            "Escalar a orientacion escolar o profesional de salud mental si aparecen ideas autolesivas o empeora el retraimiento.",
        ],
        timeline=[
            TimelineEvent(
                id="t1",
                time="08:41",
                title="Escalada verbal en grupo",
                detail='Tres mensajes consecutivos con frases de rechazo como "nadie te quiere aqui".',
            ),
            TimelineEvent(
                id="t2",
                time="08:47",
                title="Respuesta de retirada",
                detail='La menor responde con frases breves y evita continuar: "da igual", "lo dejo".',
            ),
            TimelineEvent(
                id="t3",
                time="09:02",
                title="Resumen del modelo",
                detail="El LLM consolida senales de tristeza, aislamiento y hostilidad social sostenida.",
            ),
        ],
        promptMetrics=prompt_metrics,
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
        "distress": "Distress emocional",
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
            MetricItem(label="Toxicidad", value=f"{metrics_payload['toxicity']:.2f}", trend="senal de hostilidad"),
            MetricItem(label="Insulto", value=f"{metrics_payload['insult_score']:.2f}", trend="agresion verbal"),
            MetricItem(label="Distress", value=f"{metrics_payload['distress_signal']:.2f}", trend="malestar detectado"),
            MetricItem(label="Confianza", value=f"{metrics_payload['confidence']:.2f}", trend="fiabilidad del analisis"),
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
        else f"Nuevo nivel de riesgo: {payload.riskScore}/100."
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
    await ensure_demo_data(app.state.pool)
    app.state.alert_hub = AlertHub()
    app.state.alert_state = build_default_dashboard()
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
    sender_map = {
        "child_sofia": participants[0],
        "child_mateo": participants[1],
    }

    if conversation["viewer_display_name"] == "Mateo":
        sender_map = {
            "child_sofia": participants[1],
            "child_mateo": participants[0],
        }

    return ChildChatViewOut(
        conversationId=str(conversation["conversation_id"]),
        title=f"Chat privado: {conversation['viewer_display_name']} y {conversation['other_display_name']}",
        viewerUserId=viewer_id,
        participants=participants,
        messages=[
            ChildChatMessageOut(
                id=f"msg-{index}",
                senderId=sender_map[item["sender_key"]].id,
                senderName=sender_map[item["sender_key"]].displayName,
                text=item["text"],
                sentAt=item["sentAt"],
            )
            for index, item in enumerate(DEMO_CHAT_MESSAGES, start=1)
        ],
    )


@app.post("/api/alerts/publish", response_model=AlertEnvelope)
async def publish_alert_state(payload: ParentDashboard) -> AlertEnvelope:
    app.state.alert_state = payload
    message = AlertEnvelope(type="alert_update", payload=payload)
    await app.state.alert_hub.broadcast(message)
    await send_web_push_notifications(app, payload)
    return message


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
