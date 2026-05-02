FROM python:3.13-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      openjdk-17-jre-headless \
      curl \
      unzip \
      xvfb \
      fluxbox \
      x11vnc \
      novnc \
      websockify \
    && rm -rf /var/lib/apt/lists/*

ARG ALLURE_VERSION=2.29.0
RUN curl -fsSL -o /tmp/allure-commandline.zip \
      "https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/${ALLURE_VERSION}/allure-commandline-${ALLURE_VERSION}.zip" \
    && unzip -q /tmp/allure-commandline.zip -d /opt \
    && ln -sfn "/opt/allure-${ALLURE_VERSION}" /opt/allure \
    && ln -sfn /opt/allure/bin/allure /usr/local/bin/allure \
    && rm -f /tmp/allure-commandline.zip

# --- frontend build layer ---
FROM node:22-bookworm AS frontend-build

WORKDIR /src

COPY apps/web-ui-service/frontend/package.json /src/apps/web-ui-service/frontend/package.json
COPY apps/web-ui-service/frontend/package-lock.json /src/apps/web-ui-service/frontend/package-lock.json

WORKDIR /src/apps/web-ui-service/frontend
RUN npm ci

WORKDIR /src
COPY apps/web-ui-service/frontend /src/apps/web-ui-service/frontend
RUN cd /src/apps/web-ui-service/frontend && npm run build

# --- dependency layer (cached separately from source) ---
FROM base AS deps

COPY apps/web-ui-service/requirements.txt /app/apps/web-ui-service/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/web-ui-service/requirements.txt

RUN python -m playwright install --with-deps chromium

# --- final image ---
FROM deps AS runtime

COPY . /app
COPY --from=frontend-build /src/apps/web-ui-service/app/static/react /app/apps/web-ui-service/app/static/react

EXPOSE 8013

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "apps/web-ui-service", "--host", "0.0.0.0", "--port", "8013"]
