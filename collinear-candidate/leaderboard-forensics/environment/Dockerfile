# python:3.11-slim-bookworm, digest-pinned for reproducibility
FROM python@sha256:0bee7276f83efd4a1ee05bbbf4281d95ed28e079220a9457f25a93e3f1e3c31b

RUN pip install --no-cache-dir pytest==8.4.1

COPY workspace/ /app/workspace/

WORKDIR /app/workspace
