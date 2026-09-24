# Multi-stage Dockerfile for IDX-BEI Toolkit
# Stage 1: Build the modern React 19 Frontend SPA
FROM oven/bun:1-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install
COPY frontend/ ./
RUN bun run build

# Stage 2: Unified Python 3.13 Runtime with uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Configure uv and Python runtime
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8000 \
    HOST=0.0.0.0

# Install project root dependencies
COPY pyproject.toml uv.lock ./
COPY python/ ./python/

RUN uv sync --frozen || uv sync

# Copy pre-built frontend distribution
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Copy reference dashboard and configs
COPY dashboard/ ./dashboard/

# Prepare data storage directories
RUN mkdir -p data/timeseries data/parquet data/briefings

EXPOSE 8000

# Default entrypoint starts FastAPI REST, WebSockets & SPA dashboard
CMD ["uv", "run", "idx", "serve", "--host", "0.0.0.0", "--port", "8000"]
