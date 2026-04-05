FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the whole repo into /app (Dockerfile is in server/, context is repo root)
COPY . /app/

RUN pip install --no-cache-dir \
    "openenv-core[core]>=0.2.2" \
    "openai>=1.30.0" \
    "pydantic>=2.7.0" \
    "uvicorn[standard]>=0.30.0" \
    "fastapi>=0.111.0" \
    "httpx>=0.27.0"

ENV PYTHONPATH="/app"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
