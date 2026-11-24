# One image for the API, the outbox publisher and the worker.
# The command is chosen per service in docker-compose.yml / k8s manifests.
# Build context: repository root.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ ./

# run as a non-root user (numeric id, so Kubernetes can verify runAsNonRoot)
RUN useradd --system --uid 10001 --no-create-home app && chown -R 10001:10001 /app
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
