FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-dev.txt /app/requirements-dev.txt
COPY apps/ai-orchestrator/requirements.txt /app/apps/ai-orchestrator/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/apps/ai-orchestrator/requirements.txt \
    && python -m pip install --no-cache-dir pytest pytest-playwright playwright allure-pytest \
    && playwright install chromium

COPY . /app

WORKDIR /app/apps/ai-orchestrator

ENV PYTHONPATH=/app/apps/ai-orchestrator/src
ENV FLASK_APP=src/wsgi:app

EXPOSE 8000

CMD ["python", "-m", "flask", "run", "--host", "0.0.0.0", "--port", "8000"]
