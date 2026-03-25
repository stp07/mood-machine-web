# Stage 1: Build frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim

WORKDIR /app

# System dependencies for Essentia and audio processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends libsndfile1 ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Essentia ML models
COPY scripts/ ./scripts/
RUN python scripts/download_models.py

# Backend code
COPY backend/ ./backend/

# Frontend build output
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV MOOD_MACHINE_CONFIG=/app/config.yaml

EXPOSE 8000

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
