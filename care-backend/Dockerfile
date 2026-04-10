FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /backend

COPY care-backend/requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY care-backend/ .
COPY care-database/init.sql ./init.sql

CMD uvicorn api:app --host 0.0.0.0 --port ${BACKEND_PORT:-9010}
