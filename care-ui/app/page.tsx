"use client";

import { FormEvent, useState } from "react";

import {
  DEMO_ACCOUNTS,
  DEMO_TIMING,
  findDemoAccount,
  type ChildChatView,
  type ParentDashboard,
  type RiskLevel,
  type SessionUser,
} from "./demo-script";
import { useDemoSimulation } from "./use-demo-simulation";

type DetectedConcern = "bullying" | "grooming";

type RecommendationBlock = {
  title: string;
  intro: string;
  steps: string[];
  sections?: {
    title: string;
    items: string[];
  }[];
  avoid?: string[];
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
  if (score >= 20) return "low";
  return "none";
}

function getRiskLevelLabel(level: RiskLevel) {
  if (level === "critical") return "CRITICO";
  if (level === "high") return "ALTO";
  if (level === "medium") return "MEDIO";
  if (level === "low") return "BAJO";
  return "SIN RIESGO";
}

function getDetectedConcern(dashboard: ParentDashboard): DetectedConcern {
  const text = [dashboard.summary, dashboard.llmAnswer, ...dashboard.alerts.flatMap((alert) => [alert.title, alert.detail])]
    .join(" ")
    .toLowerCase();

  if (
    text.includes("grooming") ||
    text.includes("sexual") ||
    text.includes("chantaje") ||
    text.includes("manipul")
  ) {
    return "grooming";
  }

  return "bullying";
}

function getParentRecommendations(level: RiskLevel, concern: DetectedConcern): RecommendationBlock {
  if (concern === "grooming") {
    return {
      title: "Prioridad de seguridad",
      intro: "La situacion requiere contrastar con calma y proteger sin confrontar.",
      steps: [
        "Habla en privado y valida lo que cuente sin interrogar.",
        "Conserva pruebas relevantes sin manipularlas.",
        "Busca apoyo profesional si aparecen amenazas o presion sostenida.",
      ],
    };
  }

  if (level === "critical" || level === "high") {
    return {
      title: "Atencion prioritaria",
      intro: "La prioridad es escuchar, validar y activar apoyo sin enfrentar a Sofia al conflicto en caliente.",
      steps: [
        "Habla hoy con Sofia en un entorno privado y sin interrupciones.",
        "Valida lo ocurrido antes de pedir detalles o buscar responsables.",
        "Contrasta si la exclusion se repite en clase, recreo u otros chats.",
        "Coordina con el centro si confirma repeticion o evitacion escolar.",
      ],
      sections: [
        {
          title: "Puedes decir",
          items: [
            "Te creo.",
            "No es tu culpa.",
            "Gracias por contarmelo.",
            "Vamos a buscar ayuda juntas.",
          ],
        },
      ],
      avoid: [
        "No minimices el problema como cosas de ninos.",
        "No reacciones con rabia delante de ella.",
        "No la enfrentes directamente al agresor sin plan.",
      ],
    };
  }

  if (level === "medium") {
    return {
      title: "Seguimiento recomendado",
      intro: "Se recomienda revisar con calma si la exclusion se esta convirtiendo en un patron sostenido.",
      steps: [
        "Observa cambios en animo, sueno, ganas de ir al colegio o relaciones.",
        "Abre una conversacion suave sin decir que ya conoces la alerta.",
        "Pregunta si hay alguien que la este dejando fuera o haciendo sentir mal.",
      ],
      avoid: [
        "No conviertas la conversacion en un interrogatorio.",
        "No prometas resolverlo antes de entender lo que pasa.",
      ],
    };
  }

  return {
    title: "Observacion preventiva",
    intro: "Por ahora conviene observar sin invadir y mantener una puerta abierta para hablar.",
    steps: [
      "Mantener acompanamiento cotidiano sin dramatizar.",
      "Revisar si la interaccion cambia en las proximas semanas.",
      "Volver a evaluar si aparecen rechazo o burlas repetidas.",
    ],
  };
}

function ParentPortal({
  dashboard,
  onLogout,
}: {
  dashboard: ParentDashboard;
  onLogout: () => void;
}) {
  const currentRiskLevel = getRiskLevelFromScore(dashboard.riskScore);
  const recommendationBlock = getParentRecommendations(currentRiskLevel, getDetectedConcern(dashboard));

  return (
    <>
      <header className="app-topbar app-topbar-compact">
        <div>
          <p className="app-kicker">CareNest Demo</p>
          <h1>Seguimiento familiar</h1>
          <p className="topbar-subtitle">Simulacion frontend sincronizada entre chat y panel de tutora.</p>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">Estado actual</p>
          <h2>{dashboard.riskLabel}</h2>
          <p className="hero-copy">{dashboard.summary}</p>
          <div className="hero-meta">
            <span>Ultima actualizacion: {dashboard.updatedAt}</span>
            <span>Ventana demo: febrero a abril de 2026</span>
          </div>
        </div>
        <div className={`hero-score risk-box-${riskTone(currentRiskLevel)}`}>
          <span>Nivel de seguimiento</span>
          <strong>{getRiskLevelLabel(currentRiskLevel)}</strong>
          <small>Seguimiento activo para {dashboard.teenName}</small>
        </div>
      </section>

      <section className="grid">
        <article className="card card-spotlight parent-card-profile">
          <p className="eyebrow">Perfil de seguimiento</p>
          <div className="spotlight-header">
            <div>
              <h2>{dashboard.teenName}</h2>
            </div>
            <div className="spotlight-badge">{dashboard.riskLabel}</div>
          </div>
          <p className="summary">{dashboard.llmAnswer}</p>
        </article>

        <article className="card parent-card-observations">
          <p className="eyebrow">Metricas mock</p>
          <div className="section-heading">
            <p>{dashboard.summary}</p>
          </div>
          <div className="signal-chip-list">
            {dashboard.alerts.map((alert) => (
              <span key={alert.id} className={`signal-chip ${riskTone(alert.level)}`}>
                {alert.title}
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
          <details className={`card card-guidance guidance-${currentRiskLevel} parent-disclosure`} open>
            <summary>
              <span className="eyebrow">Que puedes hacer ahora</span>
              <span className="disclosure-title">{recommendationBlock.title}</span>
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

          <details className="card card-timeline parent-disclosure" open>
            <summary>
              <span className="eyebrow">Linea temporal</span>
              <span className="disclosure-title">Evolucion del caso a lo largo de varias semanas.</span>
            </summary>
            <div className="timeline">
              {dashboard.timeline.slice(0, 5).map((event) => (
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
          Cerrar sesion
        </button>
      </footer>
    </>
  );
}

function LoginScreen({
  email,
  password,
  error,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  onUseDemoAccount,
}: {
  email: string;
  password: string;
  error: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onUseDemoAccount: (user: SessionUser & { password: string }) => void;
}) {
  return (
    <section className="login-shell">
      <div className="login-brand">
        <img src="/logo.png" alt="CareNest" className="login-logo" />
      </div>

      <article className="card login-card">
        <h2>Iniciar sesion</h2>
        <p className="hero-copy">La demo usa un guion local en frontend. No necesita backend, websocket ni datos reales.</p>
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
          <button type="submit" className="notify-button">
            Entrar
          </button>
        </form>

        <div className="login-demo-accounts">
          <p className="eyebrow">Credenciales demo</p>
          {DEMO_ACCOUNTS.map((account) => (
            <div key={account.id} className="demo-account-row">
              <p>
                {account.label}: {account.email} / {account.password}
              </p>
              <button type="button" className="text-button" onClick={() => onUseDemoAccount(account)}>
                Usar
              </button>
            </div>
          ))}
        </div>
      </article>

      <footer className="login-footer">
        <p>Escenario demo: conversacion entre menores desde febrero hasta abril de 2026.</p>
      </footer>
    </section>
  );
}

function ChildChatPortal({
  chat,
  onLogout,
}: {
  chat: ChildChatView | null;
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
          <span>historial demo</span>
        </div>
        <div className="wa-actions">
          <button type="button" className="wa-action-icon" aria-label="Demo activa">
            ▶
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

      <div className="wa-composer demo-composer-disabled">
        <span className="wa-plus">+</span>
        <input type="text" value="" readOnly placeholder="La conversacion se reproduce sola en esta demo" autoComplete="off" />
        <button type="button" className="wa-send" aria-label="Reproduccion automatica" disabled>
          ▷
        </button>
      </div>
    </section>
  );
}

function DemoControls({
  status,
  speed,
  currentPhaseIndex,
  totalPhases,
  currentPhaseTitle,
  onStart,
  onPause,
  onReset,
  onJumpToPhase,
  onSpeedChange,
}: {
  status: "idle" | "running" | "paused" | "completed";
  speed: number;
  currentPhaseIndex: number;
  totalPhases: number;
  currentPhaseTitle: string;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  onJumpToPhase: (phaseIndex: number) => void;
  onSpeedChange: (value: number) => void;
}) {
  const canGoBack = currentPhaseIndex >= 0;
  const canGoForward = currentPhaseIndex < totalPhases - 1;

  return (
    <aside className="demo-controls">
      <p className="eyebrow">Panel demo</p>
      <h3>{currentPhaseTitle}</h3>
      <p className="demo-controls-copy">
        Estado: <strong>{status}</strong> · Fase {Math.max(currentPhaseIndex + 1, 0)} / {totalPhases}
      </p>

      <div className="demo-controls-actions">
        <button type="button" className="notify-button" onClick={onStart} disabled={status === "running"}>
          {status === "completed" ? "Finalizada" : status === "paused" ? "Reanudar" : "Iniciar"}
        </button>
        <button type="button" className="notify-button secondary" onClick={onPause} disabled={status !== "running"}>
          Pausar
        </button>
        <button type="button" className="notify-button secondary" onClick={onReset}>
          Reiniciar
        </button>
      </div>

      <div className="demo-phase-jumps">
        <button type="button" className="text-button" onClick={() => onJumpToPhase(currentPhaseIndex - 1)} disabled={!canGoBack}>
          Fase anterior
        </button>
        <button type="button" className="text-button" onClick={() => onJumpToPhase(currentPhaseIndex + 1)} disabled={!canGoForward}>
          Siguiente fase
        </button>
      </div>

      <label className="field demo-speed-field">
        <span>Velocidad</span>
        <select value={String(speed)} onChange={(event) => onSpeedChange(Number(event.target.value))}>
          {DEMO_TIMING.SPEED_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}x
            </option>
          ))}
        </select>
      </label>
    </aside>
  );
}

export default function HomePage() {
  const [selectedSession, setSelectedSession] = useState<SessionUser | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const demo = useDemoSimulation();

  const chatView = selectedSession?.role === "child" ? demo.getChatViewForUser(selectedSession.id) : null;

  function handleUseDemoAccount(account: SessionUser & { password: string }) {
    setEmail(account.email);
    setPassword(account.password);
    setLoginError("");
  }

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const account = findDemoAccount(email, password);

    if (!account) {
      setLoginError("Correo o clave incorrectos.");
      return;
    }

    setSelectedSession({
      id: account.id,
      displayName: account.displayName,
      role: account.role,
      email: account.email,
    });
    setPassword("");
    setLoginError("");
  }

  function logout() {
    setSelectedSession(null);
    setLoginError("");
  }

  const currentPhaseTitle = demo.currentPhase?.title ?? "Estado inicial";

  if (selectedSession?.role === "child") {
    return (
      <>
        <main className="whatsapp-stage">
          <ChildChatPortal chat={chatView} onLogout={logout} />
        </main>
        <DemoControls
          status={demo.status}
          speed={demo.speed}
          currentPhaseIndex={demo.currentPhaseIndex}
          totalPhases={demo.totalPhases}
          currentPhaseTitle={currentPhaseTitle}
          onStart={demo.start}
          onPause={demo.pause}
          onReset={demo.reset}
          onJumpToPhase={demo.jumpToPhase}
          onSpeedChange={demo.setSpeed}
        />
      </>
    );
  }

  return (
    <>
      <main className={`dashboard-shell ${!selectedSession ? "login-page-shell" : ""}`}>
        <div className={`app-frame ${!selectedSession ? "login-page-frame" : ""}`}>
          {!selectedSession ? (
            <LoginScreen
              email={email}
              password={password}
              error={loginError}
              onEmailChange={setEmail}
              onPasswordChange={setPassword}
              onSubmit={handleLogin}
              onUseDemoAccount={handleUseDemoAccount}
            />
          ) : (
            <ParentPortal dashboard={demo.dashboard} onLogout={logout} />
          )}
        </div>
      </main>
      <DemoControls
        status={demo.status}
        speed={demo.speed}
        currentPhaseIndex={demo.currentPhaseIndex}
        totalPhases={demo.totalPhases}
        currentPhaseTitle={currentPhaseTitle}
        onStart={demo.start}
        onPause={demo.pause}
        onReset={demo.reset}
        onJumpToPhase={demo.jumpToPhase}
        onSpeedChange={demo.setSpeed}
      />
    </>
  );
}
