ARG PYTHON_VERSION="3.11-slim"

FROM python:${PYTHON_VERSION} AS base

# Image defaults. Stages inherit these values so configuration stays in one place.

# VIRTUAL_ENV: virtualenv location copied from builder to runtime; use another absolute path only if the copy paths also change.
ENV VIRTUAL_ENV=/opt/venv

# PATH: makes the virtualenv's Python and console scripts take priority; prepend more paths here if needed.
ENV PATH="/opt/venv/bin:${PATH}"

# PORT: HTTP listen port read by the server; set to any valid TCP port, or let platforms like Heroku override it.
ENV PORT=5000

# VOICE: default Piper voice id or model path; examples: en_US-lessac-low, en_US-hfc_male-medium, /models/voice.onnx.
ENV VOICE=en_US-hfc_male-medium

# DATA_DIR: model search directory list; on Linux, multiple paths can be separated with ':' such as /models:/extra-models.
ENV DATA_DIR=/models

# ALIGNMENT_METHOD: timestamp engine; valid values are forced_ctc or silence.
ENV ALIGNMENT_METHOD=forced_ctc

# FORCED_ALIGNER_BUNDLE: torchaudio ASR bundle used by forced_ctc; choose another compatible torchaudio.pipelines bundle if needed.
ENV FORCED_ALIGNER_BUNDLE=WAV2VEC2_ASR_BASE_960H

# FORCED_ALIGNER_MIN_WORD_SCORE: minimum per-word alignment confidence; 0.0 accepts all, higher values reject weak matches.
ENV FORCED_ALIGNER_MIN_WORD_SCORE=0.0

# PYTHONUNBUFFERED: stream logs immediately to container stdout/stderr; set 0 or unset to allow buffering.
ENV PYTHONUNBUFFERED=1

# PYTHONDONTWRITEBYTECODE: avoid writing .pyc files into the container filesystem; set 0 or unset to enable bytecode files.
ENV PYTHONDONTWRITEBYTECODE=1

# MALLOC_ARENA_MAX: limits how many memory pools glibc creates.
# Keep 1 for small containers to reduce RAM usage; higher values can improve heavy multi-threaded throughput at the cost of memory.
ENV MALLOC_ARENA_MAX=1

# OMP_NUM_THREADS: caps OpenMP worker threads used by native math/audio libraries.
# Keep 1 on small CPU limits to avoid thread contention; try 2, 4, or the container CPU count for larger machines.
ENV OMP_NUM_THREADS=1

# OPENBLAS_NUM_THREADS: caps OpenBLAS math threads, which some Python/native packages may use under the hood.
# Keep 1 for predictable latency; raise only when benchmarks show faster synthesis on multi-core containers.
ENV OPENBLAS_NUM_THREADS=1

# PIPER_MAX_LOADED_VOICES: number of Piper voice models kept loaded in RAM.
# 0 saves memory but reloads every request; 1 is best for one default voice; higher values speed up apps that switch voices often.
ENV PIPER_MAX_LOADED_VOICES=1

# PIPER_INTRA_OP_THREADS: ONNX Runtime threads used inside a single model operation.
# Keep 1 for small/shared CPUs; try 2 or more on dedicated multi-core hosts if one request should finish faster.
ENV PIPER_INTRA_OP_THREADS=1

# PIPER_INTER_OP_THREADS: ONNX Runtime threads used to run independent model operations at the same time.
# Usually 1 is simplest and most stable; increase only together with PIPER_EXECUTION_MODE=parallel after measuring.
ENV PIPER_INTER_OP_THREADS=1

# PIPER_EXECUTION_MODE: ONNX execution strategy.
# sequential uses fewer threads and steadier memory; parallel can use more CPU to improve throughput on larger machines.
ENV PIPER_EXECUTION_MODE=sequential

# PIPER_ENABLE_CPU_MEM_ARENA: lets ONNX keep a reusable CPU memory pool instead of asking the OS each time.
# 1/true is usually faster but may hold memory longer; 0/false can lower retained memory in very tight containers.
ENV PIPER_ENABLE_CPU_MEM_ARENA=1

# PIPER_ENABLE_MEM_PATTERN: lets ONNX remember allocation patterns for repeated model runs.
# 1/true usually improves repeated synthesis speed; 0/false is a troubleshooting option for unusual memory behavior.
ENV PIPER_ENABLE_MEM_PATTERN=1

# SYNTHESIS_CONCURRENCY: how many synthesis requests a worker may run at the same time.
# 1 protects CPU/RAM and gives stable latency; raise only when the container has enough cores and memory for parallel requests.
ENV SYNTHESIS_CONCURRENCY=1

# SYNTHESIS_ACQUIRE_TIMEOUT_SECONDS: how long a request waits for a free synthesis slot before returning HTTP 503.
# Lower values fail fast under load; higher values make clients wait longer instead of retrying immediately.
ENV SYNTHESIS_ACQUIRE_TIMEOUT_SECONDS=5

# MAX_WAITING_SYNTHESIS_REQUESTS: how many extra requests may wait in line when all synthesis slots are busy.
# 0 rejects immediately; small values protect memory; larger values smooth bursts but can increase user-visible wait time.
ENV MAX_WAITING_SYNTHESIS_REQUESTS=2


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
