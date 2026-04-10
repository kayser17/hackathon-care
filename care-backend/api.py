import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class PacienteCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    documento: str | None = Field(default=None, max_length=40)
    fecha_nacimiento: date | None = None


class PacienteOut(BaseModel):
    id: int
    nombre: str
    documento: str | None
    fecha_nacimiento: date | None
    creado_en: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no esta configurada")

    # Compatibilidad con DSN estilo SQLAlchemy heredado.
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    app.state.pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(title="Care Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    pool = app.state.pool
    await pool.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/api/pacientes", response_model=list[PacienteOut])
async def listar_pacientes() -> list[dict[str, Any]]:
    pool = app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, nombre, documento, fecha_nacimiento, creado_en
        FROM pacientes
        ORDER BY id DESC
        """
    )
    return [dict(row) for row in rows]


@app.post("/api/pacientes", response_model=PacienteOut, status_code=201)
async def crear_paciente(payload: PacienteCreate) -> dict[str, Any]:
    pool = app.state.pool
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO pacientes (nombre, documento, fecha_nacimiento)
            VALUES ($1, $2, $3)
            RETURNING id, nombre, documento, fecha_nacimiento, creado_en
            """,
            payload.nombre,
            payload.documento,
            payload.fecha_nacimiento,
        )
    except asyncpg.exceptions.UniqueViolationError as exc:
        raise HTTPException(status_code=409, detail="El documento ya existe") from exc

    if row is None:
        raise HTTPException(status_code=500, detail="No se pudo crear el paciente")

    return dict(row)
