"use client";

import { useEffect, useState } from "react";

type Estado = "cargando" | "ok" | "error";

export default function HomePage() {
  const [estado, setEstado] = useState<Estado>("cargando");
  const [mensaje, setMensaje] = useState("Conectando con backend...");

  useEffect(() => {
    fetch("/api/health")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const body = (await response.json()) as { status?: string };
        if (body.status === "ok") {
          setEstado("ok");
          setMensaje("Backend operativo");
          return;
        }
        throw new Error("Respuesta inesperada del backend");
      })
      .catch((error: unknown) => {
        setEstado("error");
        setMensaje(`No disponible: ${String(error)}`);
      });
  }, []);

  return (
    <main>
      <section className="panel">
        <span className="badge">Hackathon Salud</span>
        <h1>Care MVP</h1>
        <p>
          Base funcional para arrancar rapido: infraestructura limpia, backend FastAPI
          y frontend Next.js con chequeo de conectividad.
        </p>
        <div className={`status ${estado === "ok" ? "ok" : ""} ${estado === "error" ? "error" : ""}`}>
          <strong>Estado backend:</strong> {mensaje}
        </div>
        <p>
          <small>
            Usa este punto de partida para agregar modulos de pacientes, citas e historial clinico.
          </small>
        </p>
      </section>
    </main>
  );
}
