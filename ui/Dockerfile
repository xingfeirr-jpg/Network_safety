# Project 17 analysis UI (self-contained: everything it reads is inside ui/).
# Build:  docker build -t project17-ui ui
FROM docker:27-cli AS dockercli

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1

# Docker CLI only (no daemon): live runs start the replication container on the host
# through the mounted /var/run/docker.sock.
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app
COPY requirements.txt .
ARG PIP_INDEX_URL=
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} -r requirements.txt
COPY . .

# Writable runtime data (source cache + live runs). docker-compose.yml overrides this.
ENV P17_RUNTIME_DIR=/app/runtime
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
# One worker only: live-run state is kept in memory.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
