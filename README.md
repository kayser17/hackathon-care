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
