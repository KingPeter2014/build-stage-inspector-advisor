FROM python:3.11-slim

LABEL maintainer="llmops-team"
LABEL description="Build Stage Inspector Advisor OSS gateway"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Open-source runtime dependencies
COPY providers/open_source/requirements.txt ./provider_requirements.txt
RUN pip install --no-cache-dir -r provider_requirements.txt

# Application code
COPY . .

RUN printf '%s\n' \
      '#!/bin/sh' \
      'exec uvicorn serving.gateway.app:app --host 0.0.0.0 --port 4000 --workers "${UVICORN_WORKERS:-2}"' \
    > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

RUN useradd -m -u 1000 llmops && chown -R llmops:llmops /app
USER llmops

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:4000/health

ENTRYPOINT ["/app/entrypoint.sh"]
