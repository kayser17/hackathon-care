"use client";

import { formatChatStamp, formatTimelineDate, formatUpdatedAt } from "./demo-date";

export type RiskLevel = "critical" | "high" | "medium" | "low" | "none";
export type SessionRole = "guardian" | "child";

export type Alert = {
  id: string;
  title: string;
  detail: string;
  level: RiskLevel;
};

export type Metric = {
  label: string;
  value: string;
  helper: string;
};

export type TimelineEvent = {
  id: string;
  time: string;
  title: string;
  detail: string;
};

export type ParentDashboard = {
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

export type SessionUser = {
  id: string;
  displayName: string;
  role: SessionRole;
  email: string;
};

export type DemoAccount = SessionUser & {
  label: string;
  password: string;
};

export type ChildChatParticipant = {
  id: string;
  displayName: string;
};

export type ChildChatMessage = {
  id: string;
  senderId: string;
  senderName: string;
  text: string;
  sentAt: string;
};

export type ChildChatView = {
  conversationId: string;
  title: string;
  viewerUserId: string;
  participants: ChildChatParticipant[];
  messages: ChildChatMessage[];
};

export type ScriptedChatMessage = {
  id: string;
  senderId: string;
  text: string;
  isoAt: string;
};

export type DemoPhase = {
  id: string;
  title: string;
  messages: ScriptedChatMessage[];
  dashboard: ParentDashboard;
  gapStartMs: number;
  gapEndMs: number;
  pauseAfterMs: number;
  dashboardLagMs: number;
};

export type DemoScenario = {
  conversationId: string;
  teenName: string;
  guardian: DemoAccount;
  targetChild: DemoAccount;
  aggressorChild: DemoAccount;
  participants: ChildChatParticipant[];
  initialMessages: ScriptedChatMessage[];
  initialDashboard: ParentDashboard;
  phases: DemoPhase[];
};

export const DEMO_TIMING = {
  AUTO_START: false,
  INITIAL_DELAY_MS: 1200,
  DEFAULT_PHASE_PAUSE_MS: 2200,
  DEFAULT_DASHBOARD_LAG_MS: 850,
  DEFAULT_SPEED: 1,
  SPEED_OPTIONS: [0.75, 1, 1.5, 2],
} as const;

export const DEMO_GUARDIAN: DemoAccount = {
  id: "guardian-laura",
  displayName: "Laura Martinez",
  role: "guardian",
  email: "laura.martinez@care.local",
  password: "laura123",
  label: "Tutora",
};

export const DEMO_TARGET_CHILD: DemoAccount = {
  id: "child-sofia",
  displayName: "Sofia Martinez",
  role: "child",
  email: "sofia.martinez@care.local",
  password: "sofia123",
  label: "Menor objetivo",
};

export const DEMO_AGGRESSOR_CHILD: DemoAccount = {
  id: "child-diego",
  displayName: "Diego Ramos",
  role: "child",
  email: "diego.ramos@care.local",
  password: "diego123",
  label: "Otro menor",
};

export const DEMO_ACCOUNTS = [DEMO_GUARDIAN, DEMO_TARGET_CHILD, DEMO_AGGRESSOR_CHILD] as const;

function metric(label: string, value: string, helper: string): Metric {
  return { label, value, helper };
}

function timeline(id: string, isoAt: string, title: string, detail: string): TimelineEvent {
  return {
    id,
    time: formatTimelineDate(isoAt),
    title,
    detail,
  };
}

function dashboardSnapshot({
  updatedAt,
  riskScore,
  riskLabel,
  summary,
  llmAnswer,
  alerts,
  metrics,
  timeline,
  nextSteps,
}: {
  updatedAt: string;
  riskScore: number;
  riskLabel: string;
  summary: string;
  llmAnswer: string;
  alerts: Alert[];
  metrics: Metric[];
  timeline: TimelineEvent[];
  nextSteps: string[];
}): ParentDashboard {
  return {
    teenName: DEMO_TARGET_CHILD.displayName,
    updatedAt: formatUpdatedAt(updatedAt),
    riskScore,
    riskLabel,
    summary,
    llmAnswer,
    alerts,
    metrics,
    timeline,
    nextSteps,
  };
}

const initialTimeline = [
  timeline(
    "timeline-1",
    "2026-02-12T17:08:00",
    "Interaccion habitual",
    "La conversacion empieza con tono neutral y sin indicadores relevantes de conflicto.",
  ),
];

const initialDashboard = dashboardSnapshot({
  updatedAt: "2026-02-12T17:08:00",
  riskScore: 18,
  riskLabel: "Seguimiento bajo",
  summary: "La interaccion reciente entre Sofia y Diego es breve, funcional y sin senales claras de agresion.",
  llmAnswer: "No se observan patrones de acoso. El seguimiento permanece preventivo y con metricas bajas.",
  alerts: [
    {
      id: "alert-0",
      title: "Seguimiento preventivo",
      detail: "Sin incidencias relevantes en el ultimo bloque observado.",
      level: "low",
    },
  ],
  metrics: [
    metric("Toxicidad estimada", "12%", "Lenguaje cotidiano, sin ataques directos"),
    metric("Focalizacion en Sofia", "9%", "No hay senales de hostilidad concentrada"),
    metric("Malestar emocional", "14%", "Las respuestas mantienen un tono estable"),
    metric("Confianza del analisis", "61%", "Muestra pequena y sin patrones de riesgo"),
  ],
  timeline: initialTimeline,
  nextSteps: [
    "Mantener observacion preventiva sin intervenir.",
    "Revisar solo si aparecen cambios de tono o frecuencia en las proximas semanas.",
  ],
});

const phaseOneTimeline = [
  timeline(
    "timeline-2",
    "2026-02-26T17:19:00",
    "Primeras senales de exclusion",
    "Empiezan frases para apartar a Sofia del grupo, aunque todavia sin insultos directos.",
  ),
  ...initialTimeline,
];

const phaseTwoTimeline = [
  timeline(
    "timeline-3",
    "2026-03-12T18:07:00",
    "Aumento de la hostilidad",
    "Aparecen burlas repetidas y una focalizacion mas clara sobre Sofia dentro del chat.",
  ),
  ...phaseOneTimeline,
];

const phaseThreeTimeline = [
  timeline(
    "timeline-4",
    "2026-03-27T19:13:00",
    "Escalada rapida",
    "El ritmo de mensajes sube y se consolida un patron de humillacion y amenaza de aislamiento.",
  ),
  ...phaseTwoTimeline,
];

const phaseFourTimeline = [
  timeline(
    "timeline-5",
    "2026-04-09T21:10:00",
    "Impacto emocional alto",
    "Sofia expresa cansancio emocional y rechazo a ir al colegio tras semanas de presion.",
  ),
  ...phaseThreeTimeline,
];

export const DEMO_SCENARIO: DemoScenario = {
  conversationId: "conversation-demo-bullying",
  teenName: DEMO_TARGET_CHILD.displayName,
  guardian: DEMO_GUARDIAN,
  targetChild: DEMO_TARGET_CHILD,
  aggressorChild: DEMO_AGGRESSOR_CHILD,
  participants: [
    { id: DEMO_TARGET_CHILD.id, displayName: DEMO_TARGET_CHILD.displayName },
    { id: DEMO_AGGRESSOR_CHILD.id, displayName: DEMO_AGGRESSOR_CHILD.displayName },
  ],
  initialMessages: [
    {
      id: "msg-1",
      senderId: DEMO_AGGRESSOR_CHILD.id,
      text: "Has terminado el ejercicio de mates?",
      isoAt: "2026-02-12T17:06:00",
    },
    {
      id: "msg-2",
      senderId: DEMO_TARGET_CHILD.id,
      text: "Si, casi. Luego te paso la foto.",
      isoAt: "2026-02-12T17:08:00",
    },
  ],
  initialDashboard,
  phases: [
    {
      id: "phase-1",
      title: "Primeras senales",
      gapStartMs: 2300,
      gapEndMs: 1700,
      pauseAfterMs: 2600,
      dashboardLagMs: 900,
      messages: [
        {
          id: "msg-3",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Hoy mejor haz otro grupo.",
          isoAt: "2026-02-26T17:14:00",
        },
        {
          id: "msg-4",
          senderId: DEMO_TARGET_CHILD.id,
          text: "Pensaba que ibamos juntos.",
          isoAt: "2026-02-26T17:16:00",
        },
        {
          id: "msg-5",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Mejor no, asi vamos mas rapido.",
          isoAt: "2026-02-26T17:19:00",
        },
      ],
      dashboard: dashboardSnapshot({
        updatedAt: "2026-02-26T17:19:00",
        riskScore: 33,
        riskLabel: "Seguimiento bajo",
        summary: "Empiezan mensajes de exclusion suaves hacia Sofia, aunque todavia con agresividad limitada.",
        llmAnswer: "Se observan cambios sutiles en la dinamica social: Diego marca distancia y desplaza a Sofia del grupo.",
        alerts: [
          {
            id: "alert-1",
            title: "Exclusion social incipiente",
            detail: "Aparecen mensajes para apartar a Sofia de un plan compartido.",
            level: "low",
          },
        ],
        metrics: [
          metric("Toxicidad estimada", "22%", "Sube el tono de rechazo, todavia sin insultos directos"),
          metric("Focalizacion en Sofia", "28%", "La conversacion empieza a girar sobre apartarla del grupo"),
          metric("Malestar emocional", "19%", "Sofia responde con desconcierto, sin senales fuertes de angustia"),
          metric("Confianza del analisis", "67%", "Ya hay patron inicial, aunque aun leve"),
        ],
        timeline: phaseOneTimeline,
        nextSteps: [
          "Mantener seguimiento y revisar si la exclusion se repite.",
          "Observar si Sofia empieza a evitar actividades o companias concretas.",
        ],
      }),
    },
    {
      id: "phase-2",
      title: "Burlas repetidas",
      gapStartMs: 1500,
      gapEndMs: 850,
      pauseAfterMs: 1900,
      dashboardLagMs: 750,
      messages: [
        {
          id: "msg-6",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Otra vez has venido a sentarte donde estamos.",
          isoAt: "2026-03-12T18:02:00",
        },
        {
          id: "msg-7",
          senderId: DEMO_TARGET_CHILD.id,
          text: "Solo queria estar con vosotros.",
          isoAt: "2026-03-12T18:04:00",
        },
        {
          id: "msg-8",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Siempre te pegas y luego molestas a todos.",
          isoAt: "2026-03-12T18:06:00",
        },
        {
          id: "msg-9",
          senderId: DEMO_TARGET_CHILD.id,
          text: "No hace falta que me hables asi.",
          isoAt: "2026-03-12T18:07:00",
        },
      ],
      dashboard: dashboardSnapshot({
        updatedAt: "2026-03-12T18:07:00",
        riskScore: 56,
        riskLabel: "Seguimiento recomendado",
        summary: "La conversacion muestra burlas repetidas y una focalizacion mas clara sobre Sofia como objetivo de rechazo.",
        llmAnswer: "Aumentan la hostilidad, la insistencia y el tono descalificador. Sofia empieza a responder con incomodidad explicita.",
        alerts: [
          {
            id: "alert-2",
            title: "Hostilidad repetida",
            detail: "Aparecen ataques verbales y mensajes de desvalorizacion centrados en Sofia.",
            level: "medium",
          },
        ],
        metrics: [
          metric("Toxicidad estimada", "44%", "Suben las burlas y el tono de desprecio"),
          metric("Focalizacion en Sofia", "57%", "La presion se concentra en una menor concreta"),
          metric("Malestar emocional", "37%", "Sofia verbaliza que el tono le molesta"),
          metric("Confianza del analisis", "78%", "Se consolidan patrones conversacionales de riesgo"),
        ],
        timeline: phaseTwoTimeline,
        nextSteps: [
          "Preparar una conversacion tranquila con Sofia si el patron continua.",
          "Revisar si los comentarios se repiten tambien en clase o en otros canales.",
        ],
      }),
    },
    {
      id: "phase-3",
      title: "Escalada rapida",
      gapStartMs: 620,
      gapEndMs: 260,
      pauseAfterMs: 1600,
      dashboardLagMs: 650,
      messages: [
        {
          id: "msg-10",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Te dije que no te queremos en el grupo.",
          isoAt: "2026-03-27T19:11:00",
        },
        {
          id: "msg-11",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Das vergüenza y luego te haces la victima.",
          isoAt: "2026-03-27T19:11:30",
        },
        {
          id: "msg-12",
          senderId: DEMO_TARGET_CHILD.id,
          text: "Para ya.",
          isoAt: "2026-03-27T19:12:00",
        },
        {
          id: "msg-13",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Si apareces mañana te vamos a dejar sola igual.",
          isoAt: "2026-03-27T19:12:20",
        },
        {
          id: "msg-14",
          senderId: DEMO_TARGET_CHILD.id,
          text: "Llevas dias con lo mismo.",
          isoAt: "2026-03-27T19:13:00",
        },
      ],
      dashboard: dashboardSnapshot({
        updatedAt: "2026-03-27T19:13:00",
        riskScore: 84,
        riskLabel: "Alerta prioritaria",
        summary: "La interaccion escala con rapidez: aparecen humillacion abierta, amenazas de aislamiento y respuestas defensivas de Sofia.",
        llmAnswer: "El patron ya es compatible con bullying relacional sostenido. La intensidad y la velocidad de los mensajes aumentan de forma clara.",
        alerts: [
          {
            id: "alert-3",
            title: "Bullying relacional en escalada",
            detail: "Insultos y amenaza de dejar sola a Sofia dentro del grupo.",
            level: "high",
          },
        ],
        metrics: [
          metric("Toxicidad estimada", "73%", "Se intensifican insultos, humillacion y rechazo directo"),
          metric("Focalizacion en Sofia", "81%", "La conversacion se centra en aislar a Sofia del grupo"),
          metric("Malestar emocional", "63%", "Las respuestas son mas breves y con mayor desgaste emocional"),
          metric("Confianza del analisis", "89%", "Patron consistente y repetido a lo largo de varias semanas"),
        ],
        timeline: phaseThreeTimeline,
        nextSteps: [
          "Hablar hoy con Sofia en privado y validar lo que esta ocurriendo.",
          "Preparar coordinacion con tutoria si se confirma repeticion fuera del chat.",
        ],
      }),
    },
    {
      id: "phase-4",
      title: "Impacto emocional",
      gapStartMs: 1100,
      gapEndMs: 2600,
      pauseAfterMs: 0,
      dashboardLagMs: 900,
      messages: [
        {
          id: "msg-15",
          senderId: DEMO_AGGRESSOR_CHILD.id,
          text: "Mejor ni vengas mañana.",
          isoAt: "2026-04-09T21:02:00",
        },
        {
          id: "msg-16",
          senderId: DEMO_TARGET_CHILD.id,
          text: "Entre clase y tus mensajes me haces sentir fatal.",
          isoAt: "2026-04-09T21:05:00",
        },
        {
          id: "msg-17",
          senderId: DEMO_TARGET_CHILD.id,
          text: "Ya no quiero ir.",
          isoAt: "2026-04-09T21:10:00",
        },
      ],
      dashboard: dashboardSnapshot({
        updatedAt: "2026-04-09T21:10:00",
        riskScore: 93,
        riskLabel: "Alerta critica",
        summary: "Tras varias semanas de exclusion y burlas, Sofia verbaliza un impacto emocional alto y rechazo a ir al colegio.",
        llmAnswer: "El caso muestra patron sostenido de acoso entre menores con deterioro emocional ya visible en la menor objetivo.",
        alerts: [
          {
            id: "alert-4",
            title: "Acoso relacional sostenido",
            detail: "Exclusion, humillacion repetida e impacto emocional alto en Sofia.",
            level: "critical",
          },
        ],
        metrics: [
          metric("Toxicidad estimada", "86%", "Lenguaje hostil y descalificador en el ultimo tramo"),
          metric("Focalizacion en Sofia", "92%", "La agresion se concentra casi por completo en Sofia"),
          metric("Malestar emocional", "79%", "Sofia expresa agotamiento y rechazo a volver al entorno escolar"),
          metric("Confianza del analisis", "94%", "El patron es estable, repetido y con impacto claro"),
        ],
        timeline: phaseFourTimeline,
        nextSteps: [
          "Hablar hoy con Sofia en privado y validar lo ocurrido antes de pedir detalles.",
          "Coordinar seguimiento con el centro si la exclusion se esta reproduciendo tambien fuera del chat.",
        ],
      }),
    },
  ],
};

export function toChildChatMessage(message: ScriptedChatMessage): ChildChatMessage {
  const sender =
    message.senderId === DEMO_TARGET_CHILD.id
      ? DEMO_TARGET_CHILD.displayName
      : DEMO_AGGRESSOR_CHILD.displayName;

  return {
    id: message.id,
    senderId: message.senderId,
    senderName: sender,
    text: message.text,
    sentAt: formatChatStamp(message.isoAt),
  };
}

export function buildChatViewForViewer(viewerId: string, messages: ScriptedChatMessage[]): ChildChatView | null {
  const viewer = DEMO_ACCOUNTS.find((account) => account.id === viewerId && account.role === "child");
  if (!viewer) return null;

  const other = viewer.id === DEMO_TARGET_CHILD.id ? DEMO_AGGRESSOR_CHILD : DEMO_TARGET_CHILD;
  return {
    conversationId: DEMO_SCENARIO.conversationId,
    title: other.displayName,
    viewerUserId: viewer.id,
    participants: DEMO_SCENARIO.participants,
    messages: messages.map(toChildChatMessage),
  };
}

export function findDemoAccount(email: string, password: string) {
  return DEMO_ACCOUNTS.find(
    (account) => account.email.toLowerCase() === email.trim().toLowerCase() && account.password === password,
  );
}
