"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildChatViewForViewer,
  DEMO_SCENARIO,
  DEMO_TIMING,
  type ChildChatView,
  type ParentDashboard,
  type ScriptedChatMessage,
} from "./demo-script";

type SimulationStatus = "idle" | "running" | "paused" | "completed";

type DemoStep =
  | {
      kind: "message";
      delayMs: number;
      phaseIndex: number;
      message: ScriptedChatMessage;
    }
  | {
      kind: "dashboard";
      delayMs: number;
      phaseIndex: number;
      dashboard: ParentDashboard;
    };

function interpolate(start: number, end: number, progress: number) {
  return Math.round(start + (end - start) * progress);
}

function buildSteps() {
  const steps: DemoStep[] = [];
  const phaseEndStepIndexes: number[] = [];

  DEMO_SCENARIO.phases.forEach((phase, phaseIndex) => {
    phase.messages.forEach((message, messageIndex) => {
      const progress = phase.messages.length <= 1 ? 1 : messageIndex / (phase.messages.length - 1);
      const gap = interpolate(phase.gapStartMs, phase.gapEndMs, progress);
      steps.push({
        kind: "message",
        delayMs:
          messageIndex === 0
            ? phaseIndex === 0
              ? DEMO_TIMING.INITIAL_DELAY_MS
              : DEMO_SCENARIO.phases[phaseIndex - 1].pauseAfterMs || DEMO_TIMING.DEFAULT_PHASE_PAUSE_MS
            : gap,
        phaseIndex,
        message,
      });

      if (messageIndex === 0) {
        steps.push({
          kind: "dashboard",
          delayMs: phase.dashboardLagMs || DEMO_TIMING.DEFAULT_DASHBOARD_LAG_MS,
          phaseIndex,
          dashboard: phase.dashboard,
        });
      }
    });

    phaseEndStepIndexes.push(steps.length);
  });

  return { steps, phaseEndStepIndexes };
}

function buildStateForPhaseIndex(phaseIndex: number) {
  const messages =
    phaseIndex < 0
      ? DEMO_SCENARIO.initialMessages
      : DEMO_SCENARIO.initialMessages.concat(
          DEMO_SCENARIO.phases.slice(0, phaseIndex + 1).flatMap((phase) => phase.messages),
        );

  const dashboard = phaseIndex < 0 ? DEMO_SCENARIO.initialDashboard : DEMO_SCENARIO.phases[phaseIndex].dashboard;

  return { messages, dashboard };
}

export function useDemoSimulation() {
  const { steps, phaseEndStepIndexes } = useMemo(buildSteps, []);
  const [status, setStatus] = useState<SimulationStatus>(DEMO_TIMING.AUTO_START ? "running" : "idle");
  const [speed, setSpeed] = useState<number>(DEMO_TIMING.DEFAULT_SPEED);
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState(-1);
  const [messages, setMessages] = useState<ScriptedChatMessage[]>(DEMO_SCENARIO.initialMessages);
  const [dashboard, setDashboard] = useState<ParentDashboard>(DEMO_SCENARIO.initialDashboard);
  const stepIndexRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const applyStep = useCallback((step: DemoStep) => {
    setCurrentPhaseIndex(step.phaseIndex);
    if (step.kind === "message") {
      setMessages((current) => current.concat(step.message));
      return;
    }
    setDashboard(step.dashboard);
  }, []);

  const scheduleNext = useCallback(() => {
    clearTimer();

    if (stepIndexRef.current >= steps.length) {
      setStatus("completed");
      return;
    }

    const nextStep = steps[stepIndexRef.current];
    timeoutRef.current = window.setTimeout(() => {
      applyStep(nextStep);
      stepIndexRef.current += 1;
      scheduleNext();
    }, Math.max(40, Math.round(nextStep.delayMs / speed)));
  }, [applyStep, clearTimer, speed, steps]);

  const start = useCallback(() => {
    setStatus((current) => {
      if (current === "running") return current;
      return stepIndexRef.current >= steps.length ? "completed" : "running";
    });
  }, [steps.length]);

  const pause = useCallback(() => {
    clearTimer();
    setStatus((current) => (current === "completed" ? current : "paused"));
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    stepIndexRef.current = 0;
    setMessages(DEMO_SCENARIO.initialMessages);
    setDashboard(DEMO_SCENARIO.initialDashboard);
    setCurrentPhaseIndex(-1);
    setStatus("idle");
  }, [clearTimer]);

  const jumpToPhase = useCallback(
    (phaseIndex: number) => {
      clearTimer();
      if (phaseIndex < 0) {
        stepIndexRef.current = 0;
        setMessages(DEMO_SCENARIO.initialMessages);
        setDashboard(DEMO_SCENARIO.initialDashboard);
        setCurrentPhaseIndex(-1);
        setStatus("paused");
        return;
      }

      const boundedPhaseIndex = Math.min(phaseIndex, DEMO_SCENARIO.phases.length - 1);
      const state = buildStateForPhaseIndex(boundedPhaseIndex);
      stepIndexRef.current = phaseEndStepIndexes[boundedPhaseIndex];
      setMessages(state.messages);
      setDashboard(state.dashboard);
      setCurrentPhaseIndex(boundedPhaseIndex);
      setStatus(stepIndexRef.current >= steps.length ? "completed" : "paused");
    },
    [clearTimer, phaseEndStepIndexes, steps.length],
  );

  useEffect(() => {
    if (status !== "running") return;
    scheduleNext();
    return clearTimer;
  }, [clearTimer, scheduleNext, status]);

  useEffect(() => {
    if (!DEMO_TIMING.AUTO_START) return;
    setStatus("running");
  }, []);

  useEffect(() => clearTimer, [clearTimer]);

  const getChatViewForUser = useCallback(
    (viewerId: string): ChildChatView | null => buildChatViewForViewer(viewerId, messages),
    [messages],
  );

  const currentPhase = currentPhaseIndex >= 0 ? DEMO_SCENARIO.phases[currentPhaseIndex] : null;

  return {
    dashboard,
    status,
    speed,
    setSpeed,
    currentPhaseIndex,
    currentPhase,
    totalPhases: DEMO_SCENARIO.phases.length,
    start,
    pause,
    reset,
    jumpToPhase,
    getChatViewForUser,
  };
}
