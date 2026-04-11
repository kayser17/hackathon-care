"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type NotificationState = "desconocido" | "granted" | "denied" | "unsupported";
type RiskLevel = "critical" | "high" | "medium" | "none" | "low";
type SessionRole = "guardian" | "child";
type DetectedConcern = "bullying" | "grooming";

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
  sections?: {
    title: string;
    items: string[];
  }[];
  avoid?: string[];
  cta?: string;
};

const NOTIFICATION_PROMPT_KEY = "care-notification-prompt-seen";

const initialDashboard: ParentDashboard = {
  teenName: "Sofia Martinez",
  updatedAt: "hoy, 20:53",
  riskScore: 78,
  riskLabel: "Atención prioritaria",
  summary:
    "Se han identificado señales compatibles con malestar emocional y cambios en la interacción social.",
  llmAnswer:
    "Se observan cambios en el comportamiento social y señales de malestar emocional reciente.",
  alerts: [{ id: "a1", title: "Malestar emocional elevado", detail: "Lenguaje de tristeza sostenida.", level: "high" }],
  metrics: [
    { label: "Bienestar emocional", value: "Requiere atención", helper: "Se observan señales de malestar reciente" },
    { label: "Interacción social", value: "Cambios detectados", helper: "Puede haber aislamiento o conflicto relacional" },
  ],
  nextSteps: [
    "Hablar hoy en un momento tranquilo y sin interrupciones.",
    "Contactar con el centro para coordinar el seguimiento.",
  ],
  timeline: [{ id: "t1", time: "20:53", title: "Señales recientes", detail: "Aparecen cambios de interacción social y malestar emocional." }],
};

function riskTone(level: RiskLevel) {
  if (level === "critical") return "critical";
  if (level === "high") return "high";
  if (level === "medium") return "medium";
  return "none";
}

function getRiskLevelFromScore(score: number): RiskLevel {
  if (score >= 90) return "critical";
  if (score >= 75) return "high";
  if (score >= 45) return "medium";
  return "none";
}

function getRiskLevelLabel(level: RiskLevel) {
  if (level === "critical") return "CRÍTICO";
  if (level === "high") return "ALTO";
  if (level === "medium") return "MEDIO";
  return "SIN RIESGO";
}

function getDetectedConcern(dashboard: ParentDashboard): DetectedConcern {
  const text = [
    dashboard.summary,
    dashboard.llmAnswer,
    dashboard.riskLabel,
    ...dashboard.alerts.flatMap((alert) => [alert.title, alert.detail]),
  ]
    .join(" ")
    .toLowerCase();

  if (
    text.includes("grooming") ||
    text.includes("manipul") ||
    text.includes("pedofil") ||
    text.includes("sexual") ||
    text.includes("abuso") ||
    text.includes("explotacion") ||
    text.includes("chantaje") ||
    text.includes("imagen")
  ) {
    return "grooming";
  }

  return "bullying";
}

function getParentRecommendations(level: RiskLevel, concern: DetectedConcern): RecommendationBlock {
  if (concern === "grooming") {
    if (level === "critical" || level === "high") {
      return {
        title: "Prioridad de seguridad",
        intro: "No confrontes ni alarmes. Habla con calma, protege, guarda evidencias y busca apoyo especializado si aparecen indicios serios.",
        steps: [
          "Revisa si hay peligro inmediato. Si puede necesitar ayuda ahora, no la dejes sola y busca apoyo urgente.",
          "No contactes con la persona sospechosa ni reveles la alerta como si fuera una prueba definitiva.",
          "Habla en un momento tranquilo con preguntas abiertas y sin acusar.",
          "Guarda informacion relevante: fechas, nombres, plataformas, mensajes y frases textuales sin manipular pruebas.",
          "Busca apoyo especializado en proteccion de menores, psicologia, centro sanitario o fuerzas de seguridad si procede.",
          "Refuerza privacidad, limita contactos preocupantes y conserva evidencias sin romper la confianza.",
        ],
        sections: [
          {
            title: "Como iniciar la conversacion",
            items: [
              "Te creo.",
              "No es tu culpa.",
              "Gracias por contarmelo.",
              "Estoy contigo.",
              "Vamos a ayudarte a estar segura.",
              "Lo importante ahora es que estes segura.",
            ],
          },
        ],
        avoid: [
          "No digas que una aplicacion lo ha detectado.",
          "No la interrogues como si fuera una investigacion policial.",
          "No la hagas repetir el relato varias veces.",
          "No enfrentes a terceros sin orientacion.",
          "No esperes a ver si se pasa si hay indicios serios.",
        ],
      };
    }

    if (level === "medium") {
      return {
        title: "Revisar con calma",
        intro: "Hay senales que conviene aclarar sin alarmar y sin convertir la conversacion en una investigacion.",
        steps: [
          "Comprueba primero si necesita ayuda inmediata.",
          "Abre una conversacion general sin mencionar la alerta.",
          "Haz preguntas abiertas sobre si se siente segura o si alguien la incomoda o presiona.",
          "Escucha sin interrumpir y valida lo que diga con calma.",
          "Anota informacion relevante y no borres ni manipules mensajes.",
          "Valora si hay contacto con un posible agresor, intercambio de imagenes, chantaje, amenazas o intento de encuentro.",
        ],
        sections: [
          {
            title: "Puedes decir",
            items: [
              "Te noto preocupada ultimamente y quiero saber como estas.",
              "Si hay algo que te hace sentir mal o incomoda, puedes contarmelo.",
              "No tienes que decirme todo ahora, solo quiero ayudarte.",
            ],
          },
        ],
        avoid: [
          "No reacciones en caliente.",
          "No digas que sabes lo que pasa.",
          "No contactes de inmediato con una posible persona sospechosa.",
        ],
      };
    }

    return {
      title: "Acompanamiento preventivo",
      intro: "Por ahora conviene observar, hablar con calma y reforzar seguridad digital sin invadir.",
      steps: [
        "Elige un momento tranquilo para preguntar como esta.",
        "Usa preguntas abiertas sobre bienestar, seguridad y personas que puedan incomodarla.",
        "Escucha sin presionar ni pedir detalles innecesarios.",
        "Revisa de forma discreta privacidad, contactos y configuraciones si hace falta.",
      ],
      sections: [
        {
          title: "Preguntas abiertas",
          items: [
            "Hay algo en tu entorno que te este molestando?",
            "Te sientes segura con las personas con las que hablas?",
            "Hay alguien que te haga sentir incomoda o te presione?",
          ],
        },
      ],
      avoid: [
        "No reveles la alerta como prueba.",
        "No conviertas la conversacion en un interrogatorio.",
      ],
    };
  }

  if (level === "critical" || level === "high") {
    return {
      title: "Atención prioritaria",
      intro: "Actúa con calma. Escuchar y acompañar es más importante que reaccionar rápido.",
      steps: [
        "Habla hoy en un momento tranquilo y sin interrupciones.",
        "Empieza con señales suaves, sin presionar ni juzgar.",
        "Haz preguntas abiertas sobre su día, relaciones y emociones.",
        "Valida lo que diga y transmite apoyo.",
        "Si confirma una situación, registra lo ocurrido con calma.",
        "Contacta con el centro para coordinar el seguimiento.",
      ],
      sections: [
        {
          title: "Cómo iniciar la conversación",
          items: [
            "Te noto diferente y me preocupa como estas.",
            "No tienes que contarmelo todo ahora.",
            "Estoy aquí para escucharte.",
            "Te creo.",
            "No es tu culpa.",
            "Vamos a buscar ayuda juntos.",
          ],
        },
        {
          title: "Si necesitas hablar con el centro",
          items: [
            "Mi hija está viviendo una situación preocupante.",
            "Necesitamos revisar qué medidas de protección pueden activarse.",
            "Queremos saber cómo se va a hacer seguimiento.",
          ],
        },
      ],
      avoid: [
        "No digas que seguro exagera.",
        "No minimices como cosas de niños.",
        "No reacciones con rabia delante de ella.",
        "No la enfrentes directamente al agresor sin plan.",
        "No conviertas la conversacion en un interrogatorio.",
      ],
    };
  }

  if (level === "medium") {
    return {
      title: "Atencion recomendada",
      intro: "Conviene abrir conversacion con suavidad, observar cambios y dejar espacio para que hable a su ritmo.",
      steps: [
        "Observa cambios como rechazo a ir al colegio, tristeza, irritabilidad, silencio, perdida de objetos o cambios de sueno.",
        "Elige un momento comodo: un paseo, la vuelta del cole, la cena o un rato sin pantallas.",
        "Abre con frases suaves y evita decir directamente que sabes que hay bullying.",
        "Usa preguntas abiertas y no la bombardees si responde poco.",
        "Si cuenta algo, escucha sin interrumpir y valida lo que diga.",
        "Si se cierra, no fuerces. Deja la puerta abierta y vuelve a intentarlo otro dia.",
      ],
      sections: [
        {
          title: "Puedes decir",
          items: [
            "Te noto un poco distinta ultimamente.",
            "Si hay algo que te preocupa, puedes contarmelo.",
            "No hace falta que me lo cuentes todo ahora, pero quiero que sepas que estoy contigo.",
            "Si algo te hace sentir mal, no tienes que llevarlo sola.",
          ],
        },
        {
          title: "Preguntas abiertas",
          items: [
            "Hay algo que te este molestando en clase o en internet?",
            "Con quien te sientes bien en el cole?",
            "Hay algun momento del dia que se te haga dificil?",
            "Ha pasado algo con algun companero o companera?",
          ],
        },
      ],
      avoid: [
        "No la culpes por no haberlo contado antes.",
        "No obligues a hablar en ese momento.",
        "No prometas que lo vas a arreglar enseguida sin entender bien lo que pasa.",
      ],
    };
  }

  return {
    title: "Seguimiento preventivo",
    intro: "Por ahora se recomienda entender sin invadir y mantener una puerta abierta para hablar.",
    steps: [
      "Observa cambios de animo, sueno, ganas de ir al colegio, dolores frecuentes o perdida de objetos.",
      "Busca un momento tranquilo y cotidiano para hablar.",
      "Empieza con una frase suave y no acusatoria.",
      "Si no quiere hablar, respeta el ritmo y vuelve a intentarlo otro dia.",
    ],
    sections: [
      {
        title: "Entrada indirecta",
        items: [
          "Que te parece lo que le pasa a ese personaje?",
          "Crees que eso ocurre en la vida real?",
          "A ti te ha pasado sentirte asi alguna vez?",
          "Si te pasara algo asi, te gustaria contarmelo?",
        ],
      },
    ],
    avoid: [
      "No lo minimices.",
      "No la interrogues.",
      "No la fuerces a hablar en ese momento.",
    ],
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
  notificationState,
  showNotificationPrompt,
  onEnableNotifications,
  onDismissNotificationPrompt,
  onLogout,
}: {
  dashboard: ParentDashboard;
  notificationState: NotificationState;
  showNotificationPrompt: boolean;
  onEnableNotifications: () => void;
  onDismissNotificationPrompt: () => void;
  onLogout: () => void;
}) {
  const currentRiskLevel = getRiskLevelFromScore(dashboard.riskScore);
  const detectedConcern = getDetectedConcern(dashboard);
  const recommendationBlock = getParentRecommendations(currentRiskLevel, detectedConcern);
  const displayTeenName = dashboard.teenName === "Sofia Martinez" ? "Sofía Martínez" : dashboard.teenName;
  return (
    <>
      {showNotificationPrompt ? (
        <section className="notification-prompt-overlay" role="dialog" aria-modal="true" aria-labelledby="notification-prompt-title">
          <article className="notification-prompt-card">
            <p className="eyebrow">Avisos importantes</p>
            <h2 id="notification-prompt-title">Activa las notificaciones</h2>
            <p>
              CareNest puede enviarte avisos cuando detecte cambios relevantes en el seguimiento de {displayTeenName}.
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
          <p className="topbar-subtitle">Consulta el estado actual y qué hacer en cada momento.</p>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">Estado actual</p>
          <h2>Atención prioritaria</h2>
          <p className="hero-copy">
            Se han detectado señales que requieren seguimiento cercano hoy.
          </p>
          <div className="hero-meta">
            <span>Última actualización: {dashboard.updatedAt}</span>
          </div>
        </div>
        <div className={`hero-score risk-box-${riskTone(currentRiskLevel)}`}>
          <span>Nivel de seguimiento</span>
          <strong>{getRiskLevelLabel(currentRiskLevel)}</strong>
          <small>Seguimiento activo recomendado</small>
        </div>
      </section>

      <section className="grid">
        <article className="card card-spotlight parent-card-profile">
          <p className="eyebrow">Perfil de seguimiento</p>
          <div className="spotlight-header">
            <div>
              <h2>{displayTeenName}</h2>
            </div>
            <div className="spotlight-badge">Atención prioritaria</div>
          </div>
          <p className="summary">{dashboard.summary}</p>
        </article>

        <article className="card parent-card-observations">
          <p className="eyebrow">Qué estamos observando</p>
          <div className="section-heading">
            <p>{dashboard.llmAnswer}</p>
          </div>
          <div className="signal-chip-list">
            {dashboard.alerts.map((alert) => (
              <span key={alert.id} className={`signal-chip ${riskTone(alert.level)}`}>
                {alert.title.replace("Distress", "Malestar")}
              </span>
            ))}
            {dashboard.metrics.map((metric) => (
              <span key={metric.label} className="signal-chip">
                {metric.label} → {metric.value}
              </span>
            ))}
          </div>
        </article>

        <div className="parent-side-stack">
          <details className={`card card-guidance guidance-${currentRiskLevel} parent-disclosure`}>
            <summary>
              <span className="eyebrow">Qué puedes hacer ahora</span>
              <span className="disclosure-title">Pasos recomendados para acompañar la situación.</span>
            </summary>

            <div className="section-heading guidance-priority">
              <p className="mini-heading">{recommendationBlock.title}</p>
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

            {recommendationBlock.sections?.map((section) => (
              <div className="guidance-section" key={section.title}>
                <h3>{section.title}</h3>
                <ul>
                  {section.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}

            {recommendationBlock.avoid?.length ? (
              <div className="guidance-avoid">
                <h3>Evita estas reacciones</h3>
                <ul>
                  {recommendationBlock.avoid.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </details>

          <details className="card card-timeline parent-disclosure" id="ultimas-actualizaciones">
            <summary>
              <span className="eyebrow">Últimas actualizaciones</span>
              <span className="disclosure-title">Eventos recientes relacionados con el seguimiento.</span>
            </summary>
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
          </details>
        </div>
      </section>

      <footer className="parent-footer">
        <button type="button" className="text-button" onClick={onLogout}>
          Cerrar sesión
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
        <img src="/logo.png" alt="CareNest" className="login-logo" />
      </div>

      <article className="card login-card">
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

      <footer className="login-footer">
        <p>Copyright (c) 2026 CareNest. Todos los derechos reservados.</p>
      </footer>
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
    <main className={`dashboard-shell ${!selectedSession ? "login-page-shell" : ""}`}>
      <div className={`app-frame ${!selectedSession ? "login-page-frame" : ""}`}>
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
