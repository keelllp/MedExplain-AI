# MedExplain AI — backend image (FastAPI, single Uvicorn worker).
# Build from the REPO ROOT (it also needs ../knowledge_base):
#   docker build -f backend/Dockerfile -t medexplain-backend .
# OCR (PaddleOCR) is OFF by default to keep the image small + the build reliable; native-text
# PDFs work without it. Enable for scanned/image uploads with:  --build-arg INSTALL_OCR=true
FROM python:3.12-slim

# uv: fast, lockfile-pinned installs (copy the static binary from the official image).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app/backend

ARG INSTALL_OCR=false

# curl for the healthcheck; OCR needs a few GL/threading libs (only installed when enabled).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && if [ "$INSTALL_OCR" = "true" ]; then \
        apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1; \
    fi \
 && rm -rf /var/lib/apt/lists/*

# Dependency layer (cached unless the lockfile changes) — install from the frozen lock.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN if [ "$INSTALL_OCR" = "true" ]; then \
        uv sync --frozen --no-dev --extra ocr; \
    else \
        uv sync --frozen --no-dev; \
    fi

# App source + the knowledge base (read at request time; lives at PROJECT_ROOT/knowledge_base).
COPY backend/app ./app
COPY knowledge_base /app/knowledge_base

# Non-root user; /app/data is the writable state dir (mount a persistent volume here for the
# SQLite DB + uploaded files). PROJECT_ROOT resolves to /app, so data/ + vector_store/ land here.
RUN useradd -m -u 10001 app \
 && mkdir -p /app/data /app/vector_store \
 && chown -R app:app /app
USER app

ENV PATH="/app/backend/.venv/bin:$PATH" \
    MEDEXPLAIN_ENV=prod
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Single worker is load-bearing (one semaphore owns warm models; SQLite single-writer).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
