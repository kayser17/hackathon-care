"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

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
  helper: string;
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

type RecommendationBlock = {
  title: string;
  intro: string;
  steps: string[];
  avoid?: string[];
  cta?: string;
};

const NOTIFICATION_PROMPT_KEY = "care-notification-prompt-seen";

const initialDashboard: ParentDashboard = {
  teenName: "Sofia Martinez",
  updatedAt: "Hoy, 09:12",
  riskScore: 78,
  riskLabel: "Alerta prioritaria",
  summary:
    "El sistema detecta senales consistentes con aislamiento social, tristeza sostenida y comentarios de rechazo en un chat reciente.",
  llmAnswer:
    "El analisis del caso sugiere un riesgo emocional creciente. Se observan expresiones de desesperanza, retirada del grupo y una interaccion repetida donde el menor recibe mensajes descalificadores.",
  alerts: [{ id: "a1", title: "Malestar emocional elevado", detail: "Lenguaje de tristeza sostenida.", level: "high" }],
  metrics: [
    { label: "Bienestar emocional", value: "Requiere atencion", helper: "Se observan senales de malestar reciente" },
    { label: "Interaccion social", value: "Cambios detectados", helper: "Puede haber aislamiento o conflicto relacional" },
    { label: "Nivel de seguimiento", value: "Alto", helper: "Se recomienda observacion cercana" },
    { label: "Estado del caso", value: "En revision", helper: "Se actualizara si hay cambios relevantes" },
  ],
  nextSteps: [
    "Hablar con Sofia Martinez hoy en un entorno privado y sin confrontacion.",
    "Registrar cambios de sueno, apetito o aislamiento durante esta semana.",
  ],
  timeline: [{ id: "t1", time: "08:41", title: "Escalada verbal", detail: "Aparecen senales repetidas de rechazo social." }],
};

function riskTone(level: RiskLevel) {
  if (level === "high") return "critical";
  if (level === "medium") return "warning";
  return "calm";
}

function getRiskLevelFromScore(score: number): RiskLevel {
  if (score >= 75) return "high";
  if (score >= 45) return "medium";
  return "low";
}

function getParentRecommendations(level: RiskLevel): RecommendationBlock {
  if (level === "high") {
    return {
      title: "Atencion prioritaria",
      intro: "Se recomienda seguimiento cercano.",
      steps: [
        "Habla con tu hijo o hija hoy, en calma y en privado.",
        "Escucha primero y evita una conversacion centrada en culpa o vigilancia.",
        "Observa si hay aislamiento, tristeza sostenida o cambios bruscos de conducta.",
        "Contacta con orientacion o apoyo profesional si el malestar persiste o aumenta.",
      ],
      avoid: [
        "No confrontes con enfado.",
        "No revises todo su contenido privado como primera respuesta.",
        "No minimices lo que esta sintiendo.",
      ],
    };
  }

  if (level === "medium") {
    return {
      title: "Atencion recomendada",
      intro: "Se han detectado senales que conviene abordar pronto.",
      steps: [
        "Busca hoy o manana un momento tranquilo para hablar.",
        "Pregunta como se esta sintiendo sin presionar.",
        "Observa cambios en animo, sueno, energia o relaciones.",
        "Manten una revision cercana durante los proximos dias.",
      ],
      avoid: [
        "No conviertas la conversacion en un interrogatorio.",
        "No reacciones con castigos inmediatos.",
      ],
      cta: "Ver recursos de apoyo",
    };
  }

  return {
    title: "Seguimiento preventivo",
    intro: "Por ahora se recomienda observacion tranquila y apoyo cercano.",
    steps: [
      "Manten una conversacion abierta y tranquila.",
      "Observa cambios emocionales o sociales durante la semana.",
      "Refuerza rutinas, descanso y apoyo familiar.",
      "Revisa la app si aparecen nuevas actualizaciones.",
    ],
    cta: "Ver consejos de acompanamiento",
  };
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
  if (typeof window === "undefined" || !("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return "unsupported";
  }
  if (Notification.permission === "granted") return "granted";
  if (Notification.permission === "denied") return "denied";
  return "desconocido";
}

async function showRiskNotification(payload: ParentDashboard) {
  if (typeof window === "undefined" || !("Notification" in window) || Notification.permission !== "granted") {
    return;
  }

  const topAlert = payload.alerts[0];
  const body = topAlert ? `${topAlert.title}. ${topAlert.detail}` : "Hay una nueva actualizacion de seguimiento.";
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
  notificationState,
  showNotificationPrompt,
  onEnableNotifications,
  onDismissNotificationPrompt,
  onLogout,
}: {
  dashboard: ParentDashboard;
  guardianName: string;
  notificationState: NotificationState;
  showNotificationPrompt: boolean;
  onEnableNotifications: () => void;
  onDismissNotificationPrompt: () => void;
  onLogout: () => void;
}) {
  const currentRiskLevel = getRiskLevelFromScore(dashboard.riskScore);
  const recommendationBlock = getParentRecommendations(currentRiskLevel);

  return (
    <>
      {showNotificationPrompt ? (
        <section className="notification-prompt-overlay" role="dialog" aria-modal="true" aria-labelledby="notification-prompt-title">
          <article className="notification-prompt-card">
            <p className="eyebrow">Avisos importantes</p>
            <h2 id="notification-prompt-title">Activa las notificaciones</h2>
            <p>
              CareNest puede enviarte avisos cuando detecte cambios relevantes en el seguimiento de Sofia Martinez.
            </p>
            {notificationState === "unsupported" ? (
              <p>En iPhone, abre CareNest como app instalada en la pantalla de inicio para habilitar Web Push.</p>
            ) : null}
            {notificationState === "denied" ? (
              <p>El permiso esta bloqueado. Puedes cambiarlo desde los ajustes del navegador o del dispositivo.</p>
            ) : null}
            <div className="notification-prompt-actions">
              {notificationState === "desconocido" ? (
                <button type="button" className="notify-button" onClick={onEnableNotifications}>
                  Activar notificaciones
                </button>
              ) : null}
              <button type="button" className="notify-button secondary" onClick={onDismissNotificationPrompt}>
                {notificationState === "desconocido" ? "Ahora no" : "Entendido"}
              </button>
            </div>
          </article>
        </section>
      ) : null}

      <header className="app-topbar app-topbar-compact">
        <div>
          <p className="app-kicker">CareNest</p>
          <h1>Seguimiento familiar</h1>
          <p className="topbar-subtitle">Consulta el estado actual y las recomendaciones de acompanamiento.</p>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">Estado actual</p>
          <h2>{recommendationBlock.title}</h2>
          <p className="hero-copy">
            {recommendationBlock.intro}
          </p>
          <div className="hero-meta">
            <span>Ultima actualizacion: {dashboard.updatedAt}</span>
          </div>
        </div>
        <div className="hero-score">
          <span>Nivel de atencion</span>
          <strong>{currentRiskLevel === "high" ? "Alto" : currentRiskLevel === "medium" ? "Medio" : "Bajo"}</strong>
          <small>Seguimiento activo para Sofia Martinez</small>
        </div>
      </section>

      <section className="grid">
        <article className="card card-spotlight parent-card-profile">
          <p className="eyebrow">Perfil de seguimiento</p>
          <div className="spotlight-header">
            <div>
              <h2>{dashboard.teenName}</h2>
              <p className="timestamp">Ultima actualizacion: {dashboard.updatedAt}</p>
            </div>
            <div className="spotlight-badge">Atencion prioritaria</div>
          </div>
          <p className="summary">{dashboard.summary}</p>
        </article>

        <article className="card parent-card-observations">
          <p className="eyebrow">Que estamos observando</p>
          <div className="section-heading">
            <h2>Senales detectadas</h2>
            <p>{dashboard.llmAnswer}</p>
          </div>
          <div className="signal-chip-list">
            {dashboard.alerts.map((alert) => (
              <span key={alert.id} className={`signal-chip ${riskTone(alert.level)}`}>
                {alert.title.replace("Distress", "Malestar")}
              </span>
            ))}
          </div>
          <div className="metric-grid parent-metric-grid">
            {dashboard.metrics.map((metric) => (
              <section key={metric.label} className="metric-card">
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <small>{metric.helper}</small>
              </section>
            ))}
          </div>
        </article>

        <div className="parent-side-stack">
          <article className={`card card-guidance guidance-${currentRiskLevel}`}>
            <p className="eyebrow">Que hacer ahora</p>
            <div className="section-heading">
              <h2>{recommendationBlock.title}</h2>
              <p>{recommendationBlock.intro}</p>
            </div>

            <ul className="action-list">
              {recommendationBlock.steps.map((step, index) => (
                <li key={step}>
                  <span className="action-index">{index + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>

            {recommendationBlock.avoid?.length ? (
              <div className="guidance-avoid">
                <h3>Evita esto</h3>
                <ul>
                  {recommendationBlock.avoid.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>

          <article className="card card-timeline">
            <p className="eyebrow">Ultimas actualizaciones</p>
            <div className="section-heading">
              <h2>Evolucion del caso</h2>
              <p>Eventos relevantes registrados durante el periodo reciente.</p>
            </div>
            <div className="timeline">
              {dashboard.timeline.slice(0, 3).map((event) => (
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

      <footer className="parent-footer">
        <button type="button" className="text-button" onClick={onLogout}>
          Cerrar sesion
        </button>
      </footer>
    </>
  );
}

function LoginScreen({
  email,
  password,
  loading,
  error,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}: {
  email: string;
  password: string;
  loading: boolean;
  error: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="login-shell">
      <div className="login-brand">
        <img src="/icon.svg" alt="CareNest" className="login-logo" />
        <p className="login-name">CareNest</p>
      </div>

      <article className="card login-card">
        <p className="eyebrow">Acceso</p>
        <h2>Iniciar sesion</h2>
        <p className="hero-copy">Accede con tus credenciales para continuar.</p>
        <form className="login-form" onSubmit={onSubmit}>
          <label className="field">
            <span>Correo</span>
            <input type="email" value={email} onChange={(event) => onEmailChange(event.target.value)} placeholder="Correo electronico" />
          </label>
          <label className="field">
            <span>Clave</span>
            <input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder="Contrasena"
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="notify-button" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </article>
    </section>
  );
}

function ChildChatPortal({
  chat,
  draft,
  onDraftChange,
  onSend,
  onLogout,
}: {
  chat: ChildChatView | null;
  draft: string;
  onDraftChange: (value: string) => void;
  onSend: (event: FormEvent<HTMLFormElement>) => void;
  onLogout: () => void;
}) {
  if (!chat) {
    return (
      <section className="whatsapp-phone">
        <div className="wa-statusbar" />
      </section>
    );
  }

  return (
    <section className="whatsapp-phone">
      <div className="wa-statusbar" />
      <header className="wa-header">
        <button type="button" className="wa-icon-button" onClick={onLogout} aria-label="Cerrar sesion">
          &lt;
        </button>
        <div className="wa-avatar">{chat.title.slice(0, 1).toUpperCase()}</div>
        <div className="wa-contact">
          <strong>{chat.title}</strong>
          <span>en linea</span>
        </div>
        <div className="wa-actions">
          <button type="button" className="wa-action-icon" aria-label="Videollamada">
            📹
          </button>
          <button type="button" className="wa-action-icon" aria-label="Llamada">
            📞
          </button>
          <button type="button" className="wa-action-icon" aria-label="Mas opciones">
            ⋮
          </button>
        </div>
      </header>

      <div className="wa-thread">
        {chat.messages.map((message) => {
          const own = message.senderId === chat.viewerUserId;
          return (
            <section key={message.id} className={`wa-bubble ${own ? "own" : "other"}`}>
              <p>{message.text}</p>
              <span>{message.sentAt}</span>
            </section>
          );
        })}
      </div>

      <form className="wa-composer" onSubmit={onSend}>
        <span className="wa-plus">+</span>
        <input
          type="text"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="Mensaje"
          autoComplete="off"
        />
        <button type="submit" className="wa-send" aria-label="Enviar mensaje">
          &gt;
        </button>
      </form>
    </section>
  );
}

export default function HomePage() {
  const [dashboard, setDashboard] = useState(initialDashboard);
  const [selectedSession, setSelectedSession] = useState<SessionUser | null>(null);
  const [chatView, setChatView] = useState<ChildChatView | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [showNotificationPrompt, setShowNotificationPrompt] = useState(false);
  const [notificationState, setNotificationState] = useState<NotificationState>(getNotificationState());
  const [pushMessage, setPushMessage] = useState("Las notificaciones estan desactivadas.");
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

  const refreshChildChat = async (childId: string) => {
    const response = await fetch(buildBackendUrl(`/api/session/child/${childId}/chat`));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = (await response.json()) as ChildChatView;
    setChatView(body);
  };

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
          JSON.parse(event.data) as AlertEnvelope;
          void refreshGuardianDashboard(selectedSession.id).then(({ nextDashboard, riskIncreased }) => {
            if (riskIncreased) void showRiskNotification(nextDashboard);
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
    if (selectedSession?.role !== "guardian" || notificationState === "granted") return;
    if (typeof window === "undefined") return;
    if (window.localStorage.getItem(NOTIFICATION_PROMPT_KEY) === "seen") return;
    setShowNotificationPrompt(true);
  }, [selectedSession, notificationState]);

  useEffect(() => {
    if (selectedSession?.role !== "child") {
      setChatView(null);
      setChatDraft("");
      return;
    }

    void refreshChildChat(selectedSession.id).catch((error) => {
      console.error("No se pudo cargar la vista de chat", error);
    });

    const refreshTimer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void refreshChildChat(selectedSession.id).catch((error) => {
        console.error("No se pudo actualizar la vista de chat", error);
      });
    }, 6000);

    return () => window.clearInterval(refreshTimer);
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
    if (typeof window === "undefined" || !("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      setNotificationState("unsupported");
      setPushMessage("En iPhone, abre CareNest como app instalada en la pantalla de inicio para habilitar Web Push.");
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

  function markNotificationPromptSeen() {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(NOTIFICATION_PROMPT_KEY, "seen");
    }
    setShowNotificationPrompt(false);
  }

  function handleEnableNotifications() {
    markNotificationPromptSeen();
    void enableNotifications();
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginLoading(true);
    setLoginError("");

    try {
      const response = await fetch(buildBackendUrl("/api/session/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const detail = response.status === 401 ? "Correo o clave incorrectos." : "No se pudo iniciar sesion.";
        throw new Error(detail);
      }

      const user = (await response.json()) as SessionUser;
      setSelectedSession(user);
      setPassword("");
    } catch (error) {
      setLoginError(String(error instanceof Error ? error.message : error));
    } finally {
      setLoginLoading(false);
    }
  }

  function logout() {
    setSelectedSession(null);
    setChatView(null);
    setChatDraft("");
    setLoginError("");
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSession || selectedSession.role !== "child" || !chatView) return;

    const text = chatDraft.trim();
    if (!text) return;

    try {
      const response = await fetch(buildBackendUrl(`/api/session/child/${selectedSession.id}/chat/messages`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const body = (await response.json()) as ChildChatView;
      setChatView(body);
      setChatDraft("");
    } catch (error) {
      console.error("No se pudo enviar el mensaje", error);
    }
  }

  if (selectedSession?.role === "child") {
    return (
      <main className="whatsapp-stage">
        <ChildChatPortal
          chat={chatView}
          draft={chatDraft}
          onDraftChange={setChatDraft}
          onSend={handleSendMessage}
          onLogout={logout}
        />
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <div className="app-frame">
        {!selectedSession ? (
          <LoginScreen
            email={email}
            password={password}
            loading={loginLoading}
            error={loginError}
            onEmailChange={setEmail}
            onPasswordChange={setPassword}
            onSubmit={handleLogin}
          />
        ) : (
          <ParentPortal
            dashboard={dashboard}
            guardianName={selectedSession.displayName}
            notificationState={notificationState}
            showNotificationPrompt={showNotificationPrompt}
            onEnableNotifications={handleEnableNotifications}
            onDismissNotificationPrompt={markNotificationPromptSeen}
            onLogout={logout}
          />
        )}
      </div>
    </main>
  );
}
