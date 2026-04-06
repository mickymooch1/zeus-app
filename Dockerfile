# Stage 1: Build React frontend — cache bust 2026-04-06
FROM node:20-slim AS frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# Copy built dist to /web/dist — where main.py looks:
# Path(__file__).parent.parent / "web" / "dist" = /web/dist
COPY --from=frontend /web/dist /web/dist
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
