export default function OfflinePage() {
  return (
    <main className="offline-shell">
      <section className="offline-card">
        <span className="badge">Modo sin conexion</span>
        <h1>Care sigue disponible</h1>
        <p>
          No hay red en este momento. Puedes volver a abrir la app cuando recupere conexion
          para sincronizar alertas, respuesta del LLM y actualizaciones del panel.
        </p>
      </section>
    </main>
  );
}
