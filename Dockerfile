FROM python:3.11-slim AS base

FROM base AS builder

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --no-compile -r /tmp/requirements.txt && \
  rm /tmp/requirements.txt && \
  pip uninstall -y pip setuptools && \
  find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true


FROM base AS runtime

ENV VOICE=en_US-lessac-low \
  DATA_DIR=/models \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  MALLOC_ARENA_MAX=1 \
  OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 \
  PIPER_MAX_LOADED_VOICES=0 \
  PIPER_INTRA_OP_THREADS=1 \
  PIPER_INTER_OP_THREADS=1 \
  PIPER_EXECUTION_MODE=sequential \
  PIPER_ENABLE_CPU_MEM_ARENA=1 \
  PIPER_ENABLE_MEM_PATTERN=1


RUN mkdir -p /models

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY main.py /usr/local/bin/main.py
COPY src /usr/local/bin/src

RUN useradd -m -u 1000 piper && \
  chown -R piper:piper /models /usr/local/bin/main.py /usr/local/bin/src

USER piper

WORKDIR /home/piper

EXPOSE 5000

CMD ["python3", "/usr/local/bin/main.py"]
