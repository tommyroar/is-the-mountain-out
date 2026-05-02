# syntax=docker/dockerfile:1.7
# Inference container: invoked by the Cloudflare Worker on each */15 cron tick,
# or by local-runner/ on long-running hosts. Published as a multi-arch image
# (linux/amd64 for Cloudflare Containers, linux/arm64 for Apple Silicon hosts).

ARG PYTHON_VERSION=3.14

FROM python:${PYTHON_VERSION}-slim-bookworm AS deps

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_INSTALLER_METADATA=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


FROM deps AS runtime

WORKDIR /app

COPY train/ ./train/
COPY tools/ ./tools/
COPY collect/ ./collect/
COPY inference/ ./inference/
COPY mountain.toml ./

ARG MODEL_VERSION=unknown
ENV MODEL_VERSION=${MODEL_VERSION} \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" || exit 1

CMD ["uvicorn", "inference.server:app", "--host", "0.0.0.0", "--port", "8080"]
