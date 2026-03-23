FROM python:3.11-slim AS builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt

RUN python -m venv "${VIRTUAL_ENV}" && \
  pip install --no-cache-dir --no-compile -r /tmp/requirements.txt && \
  rm /tmp/requirements.txt && \
  find "${VIRTUAL_ENV}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true


FROM python:3.11-slim AS runtime

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}" \
  PORT=5000 \
  VOICE=en_US-lessac-low \
  DATA_DIR=/models \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  MALLOC_ARENA_MAX=1 \
  OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 \
  PIPER_MAX_LOADED_VOICES=1 \
  PIPER_INTRA_OP_THREADS=1 \
  PIPER_INTER_OP_THREADS=1 \
  PIPER_EXECUTION_MODE=sequential \
  PIPER_ENABLE_CPU_MEM_ARENA=1 \
  PIPER_ENABLE_MEM_PATTERN=1 \
  SYNTHESIS_CONCURRENCY=1 \
  SYNTHESIS_ACQUIRE_TIMEOUT_SECONDS=5 \
  MAX_WAITING_SYNTHESIS_REQUESTS=2

RUN apt-get update && \
  apt-get install -y --no-install-recommends ca-certificates libgomp1 && \
  rm -rf /var/lib/apt/lists/* && \
  mkdir -p /app /models

COPY --from=builder /opt/venv /opt/venv
COPY main.py /app/main.py
COPY src /app/src

RUN useradd -m -u 1000 piper && \
  chown -R piper:piper /app /models

USER piper

WORKDIR /app

EXPOSE 5000

CMD ["python", "main.py"]
