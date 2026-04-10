"use client";

import { useEffect, useRef, useState } from "react";

type NotificationState = "desconocido" | "granted" | "denied" | "unsupported";
type RiskLevel = "high" | "medium" | "low";
type SessionRole = "guardian" | "child";

type Alert = {
  id: string;
  title: string;
  detail: string;
  level: RiskLevel;
};

type Metric = {
  label: string;
  value: string;
  trend: string;
};

type TimelineEvent = {
  id: string;
  time: string;
  title: string;
  detail: string;
};

type ParentDashboard = {
  teenName: string;
  updatedAt: string;
  riskScore: number;
  riskLabel: string;
  summary: string;
  llmAnswer: string;
  alerts: Alert[];
  metrics: Metric[];
  nextSteps: string[];
  timeline: TimelineEvent[];
  promptMetrics: Record<string, string | number | Record<string, number>>;
};

type AlertEnvelope = {
  type: "snapshot" | "alert_update";
  payload: ParentDashboard;
};

type PushPublicKeyResponse = {
  publicKey: string;
};

type SessionUser = {
  id: string;
  displayName: string;
  role: SessionRole;
  email?: string | null;
};

type SessionCatalog = {
  guardians: SessionUser[];
  children: SessionUser[];
};

type SelectedSession = {
  id: string;
  displayName: string;
  role: SessionRole;
};

type ChildChatParticipant = {
  id: string;
  displayName: string;
};

type ChildChatMessage = {
  id: string;
  senderId: string;
  senderName: string;
  text: string;
  sentAt: string;
};

type ChildChatView = {
  conversationId: string;
  title: string;
  viewerUserId: string;
  participants: ChildChatParticipant[];
  messages: ChildChatMessage[];
};

const initialDashboard: ParentDashboard = {
  teenName: "Sofia",
  updatedAt: "Hoy, 09:12",
  riskScore: 78,
  riskLabel: "Alerta prioritaria",
  summary:
    "El sistema detecta senales consistentes con aislamiento social, tristeza sostenida y comentarios de rechazo en un chat reciente.",
  llmAnswer:
    "El analisis del LLM sugiere un riesgo emocional creciente. Se observan expresiones de desesperanza, retirada del grupo y una interaccion repetida donde la menor recibe mensajes descalificadores.",
  alerts: [
    { id: "a1", title: "Distress emocional elevado", detail: "Lenguaje de tristeza sostenida.", level: "high" },
  ],
  metrics: [
    { label: "Toxicidad", value: "0.68", trend: "senal de hostilidad" },
    { label: "Insulto", value: "0.72", trend: "agresion verbal" },
    { label: "Distress", value: "0.55", trend: "malestar detectado" },
    { label: "Confianza", value: "0.78", trend: "fiabilidad del analisis" },
  ],
  nextSteps: [
    "Hablar con Sofia hoy en un entorno privado y sin confrontacion.",
    "Registrar cambios de sueno, apetito o aislamiento durante esta semana.",
  ],
  timeline: [
    { id: "t1", time: "08:41", title: "Escalada verbal", detail: "Aparecen senales repetidas de rechazo social." },
  ],
  promptMetrics: {
    toxicity: 0.68,
    insult_score: 0.72,
    emotion: { anger: 0.6, sadness: 0.5, fear: 0.3 },
    manipulation_similarity: 0.81,
    targeting_intensity: 0.85,
    dominance_ratio: 0.9,
    risk_trend: "increasing",
    activity_anomaly: 0.6,
    distress_signal: 0.55,
    confidence: 0.78,
  },
};

function riskTone(level: RiskLevel) {
  if (level === "high") return "critical";
  if (level === "medium") return "warning";
  return "calm";
}

function buildSocketUrl() {
  const configured = process.env.NEXT_PUBLIC_CARE_WS_URL;
  if (configured) return configured;
  if (typeof window === "undefined") return "ws://localhost:9010/ws/alerts";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.hostname}:9010/ws/alerts`;
}

function buildBackendUrl(path: string) {
  const configured = process.env.NEXT_PUBLIC_CARE_BACKEND_URL;
  const baseUrl = configured || "http://localhost:9010";
  return `${baseUrl}${path}`;
}

function base64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const normalized = (base64String + padding).replaceAll("-", "+").replaceAll("_", "/");
  const rawData = window.atob(normalized);
  return Uint8Array.from(rawData, (char) => char.charCodeAt(0));
}

function getNotificationState(): NotificationState {
  if (typeof window === "undefined" || !("Notification" in window)) return "unsupported";
  if (Notification.permission === "granted") return "granted";
  if (Notification.permission === "denied") return "denied";
  return "desconocido";
}

function formatMetricValue(value: string | number | Record<string, number>) {
  if (typeof value === "number") return value.toFixed(2);
  if (typeof value === "string") return value;
  return Object.entries(value)
    .map(([key, nestedValue]) => `${key}: ${nestedValue.toFixed(2)}`)
    .join(" · ");
}

async function showRiskNotification(payload: ParentDashboard) {
  if (typeof window === "undefined" || !("Notification" in window) || Notification.permission !== "granted") {
    return;
  }

  const topAlert = payload.alerts[0];
  const body = topAlert ? `${topAlert.title}. ${topAlert.detail}` : `Nuevo nivel de riesgo: ${payload.riskScore}/100.`;
  const registration = await navigator.serviceWorker.getRegistration();

  if (registration) {
    await registration.showNotification(`Actualizacion sobre ${payload.teenName}`, {
      body,
      icon: "/icon.svg",
      badge: "/icon-maskable.svg",
      tag: `care-risk-${payload.teenName}`,
    });
    return;
  }

  new Notification(`Actualizacion sobre ${payload.teenName}`, { body, icon: "/icon.svg" });
}

function ParentPortal({
  dashboard,
  guardianName,
  pushMessage,
  notificationState,
  onEnableNotifications,
}: {
  dashboard: ParentDashboard;
  guardianName: string;
  pushMessage: string;
  notificationState: NotificationState;
  onEnableNotifications: () => void;
}) {
  return (
    <>
      <section className="hero">
        <div>
          <span className="badge">Guardian View</span>
          <p className="hero-copy">
            Sesion iniciada como {guardianName}. Esta vista muestra alertas, respuesta del LLM
            y metricas derivadas para el menor vinculado.
          </p>
          <div className="live-strip">
            <div>
              <strong>Notificaciones al tutor</strong>
              <span>Activa Web Push para recibir avisos incluso con la app cerrada.</span>
              <span>{pushMessage}</span>
            </div>
            <button
              type="button"
              className="notify-button"
              onClick={onEnableNotifications}
              disabled={notificationState === "granted" || notificationState === "unsupported"}
            >
              {notificationState === "granted" && "Notificaciones activas"}
              {notificationState === "denied" && "Permiso bloqueado"}
              {notificationState === "unsupported" && "No soportadas"}
              {notificationState === "desconocido" && "Activar notificaciones"}
            </button>
          </div>
        </div>
        <div className="hero-score">
          <span>Riesgo actual</span>
          <strong>{dashboard.riskScore}</strong>
          <small>{dashboard.riskLabel}</small>
        </div>
      </section>

      <section className="grid">
        <article className="card card-spotlight">
          <p className="eyebrow">Menor monitorizada</p>
          <div className="spotlight-header">
            <div>
              <h2>{dashboard.teenName}</h2>
              <p className="timestamp">Ultima actualizacion: {dashboard.updatedAt}</p>
            </div>
            <div className="spotlight-badge">Revision prioritaria</div>
          </div>
          <p className="summary">{dashboard.summary}</p>
        </article>

        <article className="card">
          <p className="eyebrow">Respuesta del LLM</p>
          <h2>Interpretacion clinica asistida</h2>
          <p className="llm-answer">{dashboard.llmAnswer}</p>
        </article>

        <div className="mobile-rail">
          <article className="card card-alerts">
            <p className="eyebrow">Alertas activas</p>
            <div className="section-heading">
              <h2>Prioridades de riesgo</h2>
              <p>Incidentes recientes ordenados por nivel de urgencia.</p>
            </div>
            <div className="alert-list">
              {dashboard.alerts.map((alert) => (
                <section key={alert.id} className={`alert-card ${riskTone(alert.level)}`}>
                  <div className="alert-header">
                    <h3>{alert.title}</h3>
                    <span>{alert.level}</span>
                  </div>
                  <p>{alert.detail}</p>
                </section>
              ))}
            </div>
          </article>

          <article className="card card-metrics">
            <p className="eyebrow">Senales cuantificadas</p>
            <div className="section-heading">
              <h2>Lectura de indicadores</h2>
              <p>Metricas clave para una revision rapida desde el movil.</p>
            </div>
            <div className="metric-grid">
              {dashboard.metrics.map((metric) => (
                <section key={metric.label} className="metric-card">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.trend}</small>
                </section>
              ))}
            </div>
            <div className="prompt-metrics">
              {Object.entries(dashboard.promptMetrics).map(([key, value]) => (
                <section key={key} className="prompt-metric-item">
                  <span>{key}</span>
                  <strong>{formatMetricValue(value)}</strong>
                </section>
              ))}
            </div>
          </article>
        </div>

        <div className="mobile-rail">
          <article className="card card-actions">
            <p className="eyebrow">Siguientes pasos</p>
            <div className="section-heading">
              <h2>Plan recomendado</h2>
              <p>Acciones concretas para ejecutar hoy y durante la semana.</p>
            </div>
            <ul className="action-list">
              {dashboard.nextSteps.map((step, index) => (
                <li key={step}>
                  <span className="action-index">{index + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="card card-timeline">
            <p className="eyebrow">Linea temporal reciente</p>
            <div className="section-heading">
              <h2>Secuencia detectada</h2>
              <p>Resumen cronologico para entender la evolucion del caso.</p>
            </div>
            <div className="timeline">
              {dashboard.timeline.map((event) => (
                <section key={event.id} className="timeline-item">
                  <span>{event.time}</span>
                  <div>
                    <h3>{event.title}</h3>
                    <p>{event.detail}</p>
                  </div>
                </section>
              ))}
            </div>
          </article>
        </div>
      </section>
    </>
  );
}

function ChildChatPortal({ session, chat }: { session: SelectedSession; chat: ChildChatView | null }) {
  if (!chat) {
    return (
      <section className="hero">
        <div>
          <span className="badge">Child View</span>
          <p className="hero-copy">Cargando conversacion simulada para {session.displayName}.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="chat-shell">
      <div className="chat-phone">
        <div className="chat-header">
          <span className="chat-app">Care Chat Demo</span>
          <h2>{chat.title}</h2>
          <p>Vista simulada de mensajeria entre menores basada en participantes de la base de datos.</p>
        </div>
        <div className="chat-thread">
          {chat.messages.map((message) => {
            const own = message.senderId === chat.viewerUserId;
            return (
              <section key={message.id} className={`chat-bubble ${own ? "own" : "other"}`}>
                <small>{message.senderName}</small>
                <p>{message.text}</p>
                <span>{message.sentAt}</span>
              </section>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default function HomePage() {
  const [dashboard, setDashboard] = useState(initialDashboard);
  const [catalog, setCatalog] = useState<SessionCatalog>({ guardians: [], children: [] });
  const [selectedSession, setSelectedSession] = useState<SelectedSession | null>(null);
  const [chatView, setChatView] = useState<ChildChatView | null>(null);
  const [notificationState, setNotificationState] = useState<NotificationState>(getNotificationState());
  const [pushMessage, setPushMessage] = useState("Push pendiente de activacion");
  const retryTimer = useRef<number | null>(null);
  const previousRisk = useRef(initialDashboard.riskScore);

  const refreshGuardianDashboard = async (guardianId: string) => {
    const response = await fetch(buildBackendUrl(`/api/session/guardian/${guardianId}/dashboard`));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const nextDashboard = (await response.json()) as ParentDashboard;
    const riskIncreased = nextDashboard.riskScore > previousRisk.current;
    previousRisk.current = nextDashboard.riskScore;
    setDashboard(nextDashboard);
    return { nextDashboard, riskIncreased };
  };

  useEffect(() => {
    fetch(buildBackendUrl("/api/session/catalog"))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = (await response.json()) as SessionCatalog;
        setCatalog(body);
      })
      .catch((error) => {
        console.error("No se pudo cargar el catalogo de sesiones", error);
      });
  }, []);

  useEffect(() => {
    if (selectedSession?.role !== "guardian") return;

    void refreshGuardianDashboard(selectedSession.id).catch((error) => {
      console.error("No se pudo cargar el dashboard del tutor", error);
    });

    let socket: WebSocket | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      socket = new WebSocket(buildSocketUrl());

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as AlertEnvelope;
          void refreshGuardianDashboard(selectedSession.id).then(({ nextDashboard, riskIncreased }) => {
            if (message.type === "alert_update" && riskIncreased) {
              void showRiskNotification(nextDashboard);
            }
          });
        } catch (error) {
          console.error("No se pudo procesar el mensaje websocket", error);
        }
      };

      socket.onclose = () => {
        if (cancelled) return;
        retryTimer.current = window.setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimer.current !== null) window.clearTimeout(retryTimer.current);
      socket?.close();
    };
  }, [selectedSession]);

  useEffect(() => {
    if (selectedSession?.role !== "child") {
      setChatView(null);
      return;
    }

    fetch(buildBackendUrl(`/api/session/child/${selectedSession.id}/chat`))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = (await response.json()) as ChildChatView;
        setChatView(body);
      })
      .catch((error) => {
        console.error("No se pudo cargar la vista de chat", error);
      });
  }, [selectedSession]);

  useEffect(() => {
    const syncExistingSubscription = async () => {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

      try {
        const registration = await navigator.serviceWorker.ready;
        const existingSubscription = await registration.pushManager.getSubscription();
        if (!existingSubscription) return;

        const response = await fetch(buildBackendUrl("/api/push/subscribe"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(existingSubscription.toJSON()),
        });

        if (response.ok) setPushMessage("Suscripcion push activa. Llegaran avisos aunque cierres la app.");
      } catch (error) {
        console.error("No se pudo sincronizar la suscripcion push", error);
      }
    };

    void syncExistingSubscription();
  }, []);

  async function enableNotifications() {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setNotificationState("unsupported");
      setPushMessage("Este navegador no soporta notificaciones push");
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission === "granted") {
      setNotificationState("granted");
      setPushMessage("Permiso concedido. Registrando suscripcion push...");

      try {
        const registration = await navigator.serviceWorker.ready;
        const keyResponse = await fetch(buildBackendUrl("/api/push/public-key"));
        if (!keyResponse.ok) throw new Error(`HTTP ${keyResponse.status}`);

        const { publicKey } = (await keyResponse.json()) as PushPublicKeyResponse;
        const subscription =
          (await registration.pushManager.getSubscription()) ??
          (await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: base64ToUint8Array(publicKey),
          }));

        const syncResponse = await fetch(buildBackendUrl("/api/push/subscribe"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(subscription.toJSON()),
        });

        if (!syncResponse.ok) throw new Error(`HTTP ${syncResponse.status}`);
        setPushMessage("Suscripcion push activa. Llegaran avisos aunque cierres la app.");
      } catch (error) {
        setPushMessage(`No se pudo registrar la suscripcion push: ${String(error)}`);
      }
      return;
    }

    if (permission === "denied") {
      setNotificationState("denied");
      setPushMessage("El permiso de notificaciones esta bloqueado en el navegador");
      return;
    }

    setNotificationState("desconocido");
  }

  return (
    <main className="dashboard-shell">
      <div className="app-frame">
        <header className="app-topbar app-topbar-compact">
          <div>
            <p className="app-kicker">Care Monitor</p>
            <h1>
              {selectedSession
                ? selectedSession.role === "guardian"
                  ? "Panel familiar"
                  : "Chat simulado entre menores"
                : "Acceso por perfil"}
            </h1>
          </div>
          {selectedSession ? (
            <button type="button" className="notify-button secondary" onClick={() => setSelectedSession(null)}>
              Cambiar sesion
            </button>
          ) : null}
        </header>

        {!selectedSession ? (
          <section className="session-grid">
            <article className="card session-card">
              <p className="eyebrow">Guardianes</p>
              <h2>Entrar como padre o tutor</h2>
              <p className="hero-copy">Usuarios cargados desde la tabla `users` con rol `guardian`.</p>
              <div className="session-list">
                {catalog.guardians.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    className="session-option"
                    onClick={() => setSelectedSession({ id: user.id, displayName: user.displayName, role: "guardian" })}
                  >
                    <strong>{user.displayName}</strong>
                    <span>{user.email || "sin email"}</span>
                  </button>
                ))}
              </div>
            </article>

            <article className="card session-card">
              <p className="eyebrow">Menores</p>
              <h2>Entrar en modo simulacion</h2>
              <p className="hero-copy">
                Usuarios `child` vinculados a conversaciones. La UI renderiza un chat tipo WhatsApp.
              </p>
              <div className="session-list">
                {catalog.children.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    className="session-option"
                    onClick={() => setSelectedSession({ id: user.id, displayName: user.displayName, role: "child" })}
                  >
                    <strong>{user.displayName}</strong>
                    <span>Vista de conversacion</span>
                  </button>
                ))}
              </div>
            </article>
          </section>
        ) : selectedSession.role === "guardian" ? (
          <ParentPortal
            dashboard={dashboard}
            guardianName={selectedSession.displayName}
            pushMessage={pushMessage}
            notificationState={notificationState}
            onEnableNotifications={() => {
              void enableNotifications();
            }}
          />
        ) : (
          <ChildChatPortal session={selectedSession} chat={chatView} />
        )}
      </div>
    </main>
  );
}
