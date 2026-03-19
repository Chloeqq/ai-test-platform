FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG ALLURE_VERSION=2.29.0

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/allure-commandline.zip \
      "https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/${ALLURE_VERSION}/allure-commandline-${ALLURE_VERSION}.zip" \
    && unzip -q /tmp/allure-commandline.zip -d /opt \
    && ln -sfn "/opt/allure-${ALLURE_VERSION}" /opt/allure \
    && ln -sfn /opt/allure/bin/allure /usr/local/bin/allure \
    && rm -f /tmp/allure-commandline.zip

COPY requirements-dev.txt /app/requirements-dev.txt
COPY apps/web-ui-service/requirements.txt /app/apps/web-ui-service/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt -r /app/apps/web-ui-service/requirements.txt
RUN python -m playwright install --with-deps chromium

COPY . /app

EXPOSE 8013

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "apps/web-ui-service", "--host", "0.0.0.0", "--port", "8013"]
