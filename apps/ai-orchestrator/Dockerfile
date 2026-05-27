FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

FROM base AS deps

COPY apps/ai-orchestrator/requirements.txt /app/apps/ai-orchestrator/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/apps/ai-orchestrator/requirements.txt

FROM deps AS runtime

COPY . /app

WORKDIR /app/apps/ai-orchestrator

ENV PYTHONPATH=/app:/app/apps/ai-orchestrator/src
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-keep-alive", "300"]
