# Base image shared by every CardDemo batch service.
# Build context is modernized/batch/. Build once and tag as carddemo-batch-base:
#   docker build -f docker/base.Dockerfile -t carddemo-batch-base .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CARDDEMO_DATA_DIR=/data \
    CARDDEMO_OUTPUT_DIR=/output

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# Default command runs the whole pipeline; per-service images override CMD.
CMD ["carddemo-pipeline"]
