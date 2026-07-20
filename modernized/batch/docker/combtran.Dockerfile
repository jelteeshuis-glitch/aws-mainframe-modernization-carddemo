# COMBTRAN service (modern equivalent of SORT+IDCAMS).
# Build context is modernized/batch/:
#   docker build -f docker/combtran.Dockerfile -t carddemo-combtran .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CARDDEMO_DATA_DIR=/data \
    CARDDEMO_OUTPUT_DIR=/output

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

CMD ["carddemo-combtran"]
