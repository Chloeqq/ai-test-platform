FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-dev.txt /app/requirements-dev.txt
COPY apps/web-ui-service/requirements.txt /app/apps/web-ui-service/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt -r /app/apps/web-ui-service/requirements.txt

COPY . /app

EXPOSE 8013

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "apps/web-ui-service", "--host", "0.0.0.0", "--port", "8013"]
