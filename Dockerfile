# syntax=docker/dockerfile:1.7
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_HTTP_TIMEOUT=300 \
    UV_HTTP_RETRIES=10 \
    UV_CONCURRENT_DOWNLOADS=4 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install the locked dependencies. Keeping the dependency files in their own
# layer lets Docker reuse this layer when only application code changes.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir --timeout=300 --retries=10 uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app ./app

CMD ["uv", "run", "--no-sync", "python", "-m", "app.main"]
