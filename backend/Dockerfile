# Backend image: FastAPI + LangGraph, deps managed by uv.
# Build context is the REPO ROOT (needs pyproject.toml + uv.lock + backend/).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install dependencies first (better layer caching), then the app.
COPY pyproject.toml uv.lock ./
COPY backend ./backend
RUN uv sync --frozen --no-dev

# The SQLite checkpoint file lives on a mounted volume (see docker-compose.yml).
ENV CHECKPOINT_DB=/app/data/checkpoints.sqlite
RUN mkdir -p /app/data

EXPOSE 8000

# Lightweight healthcheck without needing curl in the image.
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
