ARG PYTHON_VERSION="3.11-slim"

FROM python:${PYTHON_VERSION} AS base

# Image defaults. Stages inherit these values so configuration stays in one place.
ENV VIRTUAL_ENV=/opt/venv \
  PATH="/opt/venv/bin:${PATH}" \
  PORT=5000 \
  VOICE=en_US-hfc_male-medium \
  DATA_DIR=/models \
  ALIGNMENT_METHOD=forced_ctc \
  FORCED_ALIGNER_BUNDLE=WAV2VEC2_ASR_BASE_960H \
  FORCED_ALIGNER_MIN_WORD_SCORE=0.0 \
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


# Build Python dependencies once, then copy the virtualenv into the runtime image.
FROM base AS builder

COPY requirements.txt /tmp/requirements.txt

# Use PyTorch's CPU wheel index because the forced aligner depends on torch/torchaudio.
RUN python -m venv "${VIRTUAL_ENV}" \
  && pip install --no-cache-dir --no-compile \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r /tmp/requirements.txt \
  && rm /tmp/requirements.txt \
  && find "${VIRTUAL_ENV}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true


# Runtime image: application code plus only the shared libraries needed at run time.
FROM base AS runtime

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /app /models

COPY --from=builder /opt/venv /opt/venv
COPY main.py /app/main.py
COPY src /app/src

RUN useradd -m -u 1000 piper \
  && chown -R piper:piper /app /models

USER piper
WORKDIR /app

# Dockerfiles can declare the mount point, but the stable volume name is chosen
# when the container is run, for example: -v piper-models:/models.
VOLUME ["/models"]

EXPOSE 5000

ENTRYPOINT ["python"]
CMD ["main.py"]
