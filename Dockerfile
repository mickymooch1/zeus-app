# Stage 1: Build Zeus AI React frontend
FROM node:20-slim AS frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Build Zeus Beats React frontend
FROM node:20-slim AS beats-frontend
WORKDIR /web-beats
COPY web-beats/package*.json ./
RUN npm ci
COPY web-beats/ ./
RUN npm run build

# Stage 3: Python backend
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg --no-install-recommends && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# Zeus AI SPA — /web/dist
COPY --from=frontend /web/dist /web/dist
# Zeus Beats SPA — /web-beats-dist
COPY --from=beats-frontend /web-beats-dist /web-beats-dist
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
