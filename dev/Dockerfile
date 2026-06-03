# Dev-only image for the docker-compose preview (NOT part of the lab submission).
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY scripts /app/scripts

ENV APP_CONFIG_PATH=/etc/mywebapp/config.yaml
EXPOSE 3000

CMD ["bash", "-c", "python -m scripts.migration && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000"]
