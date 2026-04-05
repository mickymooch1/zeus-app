FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer-cached until requirements change)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source into the working directory
COPY backend/ .

# Railway injects $PORT at runtime; fall back to 8000 for local docker run
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
