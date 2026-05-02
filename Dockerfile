# Build with: docker build --build-arg PROVIDER=<azure|aws|gcp|open_source> -t llmops-gateway .
ARG PROVIDER=open_source

FROM python:3.11-slim

# Re-declare after FROM so the ARG is in scope for this build stage
ARG PROVIDER=open_source

LABEL maintainer="llmops-team"
LABEL description="LLMOps serving gateway"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Shared base dependencies — cached independently from provider deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Provider-specific dependencies
COPY providers/${PROVIDER}/requirements.txt ./provider_requirements.txt
RUN pip install --no-cache-dir -r provider_requirements.txt

# Application code
COPY . .

# Entrypoint selects uvicorn module + port matching each provider's Terraform config:
#   open_source → serving.gateway.app:app   port 4000
#   azure       → providers.azure...app     port 4001
#   aws         → providers.aws...app       port 4002
#   gcp         → providers.gcp...app       port 4003
RUN printf '%s\n' \
      '#!/bin/sh' \
      'case "${PROVIDER}" in' \
      '  azure) MODULE="providers.azure.serving.gateway.app:app"; PORT=4001 ;;' \
      '  aws)   MODULE="providers.aws.serving.gateway.app:app";   PORT=4002 ;;' \
      '  gcp)   MODULE="providers.gcp.serving.gateway.app:app";   PORT=4003 ;;' \
      '  *)     MODULE="serving.gateway.app:app";                 PORT=4000 ;;' \
      'esac' \
      'exec uvicorn "${MODULE}" --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS:-2}"' \
    > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

RUN useradd -m -u 1000 llmops && chown -R llmops:llmops /app
USER llmops

# Bake PROVIDER into the image so entrypoint.sh reads the right value at runtime
ENV PROVIDER=${PROVIDER}
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 4000 4001 4002 4003

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD sh -c 'case "$PROVIDER" in azure) P=4001;; aws) P=4002;; gcp) P=4003;; *) P=4000;; esac; curl -f http://localhost:$P/health'

ENTRYPOINT ["/app/entrypoint.sh"]
