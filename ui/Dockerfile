# Project 17 analysis UI.
# Build from the repository root:  docker build -f ui/Dockerfile -t project17-ui .
FROM docker:27-cli AS dockercli

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1

# Docker CLI only (no daemon): live runs start the replication container on the host
# through the mounted /var/run/docker.sock.
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app
COPY ui/requirements.txt ui/requirements.txt
ARG PIP_INDEX_URL=
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} -r ui/requirements.txt

# Read-only study data, kept in the same layout as the repository so the default paths in
# ui/config.py work unchanged.
COPY Project17_Implementation_and_Data/ Project17_Implementation_and_Data/
COPY Project17_Replication/ Project17_Replication/
COPY ui/ ui/

# Writable runtime data (cache + runs). Overridden by docker-compose.yml.
ENV P17_DATA_DIR=/data
WORKDIR /app/ui
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
# One worker only: live-run state is kept in memory.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
