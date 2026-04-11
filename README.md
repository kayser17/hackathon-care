# Care MVP

Base reutilizable para hackathon de salud con tres servicios:

- `care_database`: PostgreSQL
- `care_backend`: FastAPI
- `care_ui`: Next.js

## Requisitos

- Docker + Docker Compose

## Arranque rapido

1. Copiar variables de entorno:

	 ```bash
	 cp .env.example .env
	 ```

	 Activa el seed de demo en `.env`:

	 ```bash
	 CARE_SEED_DEMO=true
	 ```

2. Levantar el stack:

	 ```bash
	 docker compose up --build
	 ```

3. Verificar servicios:

- UI: `http://localhost:13000`
- Backend health: `http://localhost:9010/health`

## Endpoints iniciales

- `GET /health`
- `GET /api/pacientes`
- `POST /api/pacientes`

Ejemplo de creacion de paciente:

```bash
curl -X POST http://localhost:9010/api/pacientes \
	-H "Content-Type: application/json" \
	-d '{
		"nombre": "Ana Perez",
		"documento": "DNI-123",
		"fecha_nacimiento": "1990-05-20"
	}'
```

## Notas

- `care-database/init.sql` define el esquema compartido. PostgreSQL lo aplica en una base nueva y el backend tambien lo reejecuta al arrancar para recuperar volumenes ya inicializados con versiones viejas del esquema.
- La UI usa un endpoint interno (`/api/health`) que consulta el backend usando `CARE_BACKEND_URL`.

## Demo preparada

La UI incluye ahora un demo scriptado completamente en frontend. No necesita backend, websocket ni analisis en vivo para la presentacion.

La historia demo incluye:

- 1 tutora: `Laura Martinez`
- 2 menores: `Sofia Martinez` y `Diego Ramos`
- una conversacion que empieza neutra y escala durante varias semanas
- metricas mock en el dashboard de la tutora que suben en paralelo al chat
- un panel de control para iniciar, pausar, reiniciar, cambiar velocidad y saltar entre fases

Credenciales demo:

- `laura.martinez@care.local / laura123`
- `sofia.martinez@care.local / sofia123`
- `diego.ramos@care.local / diego123`

Archivos principales del guion:

- `care-ui/app/demo-script.ts`
- `care-ui/app/use-demo-simulation.ts`
- `care-ui/app/demo-date.ts`

Flujo recomendado para la presentacion:

1. Arrancar la UI y entrar con `Laura Martinez`.
2. Pulsar `Iniciar` en el panel demo para mostrar la escalada de metricas.
3. Cambiar a `Sofia Martinez` o `Diego Ramos` para enseñar la misma conversacion desde cada lado.
4. Usar `Pausar`, `Reiniciar`, `Fase anterior`, `Siguiente fase` o el selector de velocidad si necesitas ajustar el ritmo en directo.
