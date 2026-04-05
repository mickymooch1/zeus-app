FROM python:3.12-slim

WORKDIR /app

# Build-time args — set these in Railway: Service → Settings → Build Arguments
# WARNING: ENV values are visible in image metadata (docker inspect / image history).
# Rotate the key if the image is ever pushed to a public registry.
# Install dependencies first (layer-cached until requirements change)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source into the working directory
COPY backend/ .

# Railway injects $PORT at runtime; fall back to 8000 for local docker run
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level debug
