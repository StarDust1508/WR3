# wr3 API — production Dockerfile
# Multi-stage build: install deps in builder, copy to slim runtime.

# --- Stage 1: Python deps + tools ---
FROM python:3.13-slim AS builder

# System deps for asyncpg, psycopg (C extensions), and tool downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev git curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dep resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace layout (uv needs both pyproject.toml files)
COPY apps/api/pyproject.toml apps/api/uv.lock /app/apps/api/
COPY packages/audit-engine/pyproject.toml /app/packages/audit-engine/

# Copy source code
COPY packages/audit-engine/src /app/packages/audit-engine/src
COPY apps/api/src /app/apps/api/src
COPY apps/api/alembic /app/apps/api/alembic
COPY apps/api/alembic.ini /app/apps/api/alembic.ini
COPY scripts/init-db.sql /app/scripts/init-db.sql

# Install Python deps
WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Ensure directories exist for optional tools (so COPY in runtime stage always works)
RUN mkdir -p /root/.solc-select /opt/tools

# Install slither-analyzer + solc into the venv (optional — build continues if fails)
RUN . .venv/bin/activate && \
    pip install --no-cache-dir slither-analyzer solc-select && \
    solc-select install 0.8.28 && solc-select use 0.8.28 \
    || echo "WARN: slither install failed, continuing without it"

# Download aderyn binary (optional — tar.xz archive)
RUN curl -fsSL -L -o /tmp/aderyn.tar.xz \
    "https://github.com/Cyfrin/aderyn/releases/latest/download/aderyn-x86_64-unknown-linux-gnu.tar.xz" \
    && tar -xf /tmp/aderyn.tar.xz -C /opt/tools/ \
    && chmod +x /opt/tools/aderyn \
    && rm /tmp/aderyn.tar.xz \
    || echo "WARN: aderyn download failed, continuing without it"

# --- Runtime stage ---
FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash wr3

WORKDIR /app
COPY --from=builder /app /app

# Copy the venv from builder (includes slither + solc-select)
COPY --from=builder /app/apps/api/.venv /app/apps/api/.venv

# Copy solc binaries (dir always exists even if empty)
COPY --from=builder /root/.solc-select/ /home/wr3/.solc-select/

# Copy aderyn binary (dir always exists even if empty)
COPY --from=builder /opt/tools/ /usr/local/bin/

ENV PATH="/app/apps/api/.venv/bin:/home/wr3/.solc-select/artifacts/solc-0.8.28:/usr/local/bin:$PATH"
ENV PYTHONPATH="/app/apps/api/src:/app/packages/audit-engine/src"
ENV PYTHONUNBUFFERED=1

# Create writable directories for runtime artifacts
RUN mkdir -p /app/apps/api/poc-output && chown -R wr3:wr3 /app/apps/api/poc-output
RUN chown -R wr3:wr3 /home/wr3/.solc-select 2>/dev/null || true

# Alembic needs to run as root for DB migrations, then app as wr3
USER wr3
WORKDIR /app/apps/api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

CMD ["uvicorn", "wr3_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
