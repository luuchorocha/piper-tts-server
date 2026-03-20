# Piper TTS Container

Production HTTP API for [Piper](https://github.com/rhasspy/piper) text-to-speech, built with Starlette + Uvicorn. Used by Story Maker's Rails backend (`Tts::PiperClient`) to synthesize page audio.

## Architecture

```
Story Maker (Rails)            Piper Container
───────────────────           ─────────────────
Tts::PiperClient  ──POST /──▶  main.py
                                  │
                                  └─ PiperVoice (ONNX inference)
                  ◀── WAV ────
```

Voice models are **not** baked into the image — mount a volume at `/models` or use the `/download` endpoint at runtime.

## Endpoints

| Method | Path          | Description                                    |
|--------|---------------|------------------------------------------------|
| POST   | `/`           | Synthesize text → WAV audio                    |
| GET    | `/health`     | Readiness check for the default voice           |
| GET    | `/voices`     | List locally available voice models             |
| GET    | `/all-voices` | List all Piper voices from HuggingFace catalog  |
| GET    | `/playroom`   | Single-page TTS testing UI                      |
| POST   | `/download`   | Download a voice model at runtime               |

### POST `/` — Synthesis

Request body (JSON):

```json
{
  "text": "Hello world",
  "voice": "en_US-lessac-low",
  "speaker_id": 0,
  "speaker": "default",
  "sentence_silence": 0.0,
  "length_scale": 1.0,
  "noise_scale": 0.667,
  "noise_w_scale": 0.8,
  "volume": 1.0,
  "normalize_audio": true,
  "include_alignments": false
}
```

Only `text` is required. `speaker` is a named speaker string for multi-speaker voices; `speaker_id` is the numeric alternative. Request payload values override the server's CLI/env defaults for the same synthesis fields.

**Standard response** (when `include_alignments` is `false` or omitted): raw `audio/wav`.

**Alignment response** (when `include_alignments` is `true`): `application/json` with this structure:

```json
{
  "audio_base64": "<base64-encoded WAV>",
  "sample_rate": 22050,
  "alignments": {
    "phonemes": [
      {"phoneme": "h", "start": 0.0, "end": 0.05},
      {"phoneme": "ɛ", "start": 0.05, "end": 0.12}
    ],
    "words": [
      {"word": "hello", "start": 0.0, "end": 0.35, "phoneme_indices": [0, 1, 2, 3, 4]}
    ]
  }
}
```

Alignment data enables audio-to-text synchronization for lip-sync, karaoke, subtitles, etc.

### GET `/playroom`

Serves a simple browser testing page with:

- language selection grouped from `/all-voices`
- voice selection filtered by language
- editable synthesis parameters
- a text input area
- generated audio history with HTML5 players

### POST `/download`

```json
{ "voice": "en_US-lessac-medium", "force_redownload": false }
```

Rate-limited to one download at a time with a 90-second cooldown.

## Files

| File                    | Purpose                                              |
|-------------------------|------------------------------------------------------|
| `main.py`               | Thin entrypoint that launches the modular server      |
| `src/`           | Server package: CLI, routes, managers, parsers, renderers, services |
| `Dockerfile`            | Production image (python:3.11-slim)                   |
| `.dockerignore`         | Whitelist for Docker build context                    |
| `requirements.txt`      | Pinned production Python dependencies                 |
| `.python-version`       | Pins Python 3.11 for pyenv/asdf/mise                  |
| `run.sh`                | Local bootstrap: creates venv, installs deps, starts server |
| `deploy.sh`             | One-command Heroku deployment                         |

## Local Development

### Prerequisites

- Python 3.10+ (3.11 recommended)
- A Piper voice model (`.onnx` + `.onnx.json`)

### Setup

```sh
cd bin/piper-container

# Create a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run the server

```sh
# Download a voice model first (if you don't have one)
python3 -c "from piper.download_voices import download_voice; download_voice('en_US-lessac-low', '.')"

# Start the server
python3 main.py -m en_US-lessac-low --data-dir . --port 5000 --debug
```

### Test synthesis

```sh
curl -s http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -d '{"text": "The quick brown fox jumps over the lazy dog."}' \
  --output output.wav
```

## Docker

### Build

```sh
cd bin/piper-container
docker build -t piper-tts .
```

### Run locally

```sh
# With a local models directory
docker run -p 5000:5000 -v /path/to/models:/models piper-tts

# Or let it download a voice on first request
docker run -p 5000:5000 -e PIPER_ALLOW_DOWNLOADS=1 piper-tts
```

The production image binds to `0.0.0.0` and reads the listen port from `$PORT`, so the same image works locally and on Heroku without extra CLI flags.

### Verify

```sh
curl http://localhost:5000/health
```

The endpoint returns HTTP `200` when the configured default voice is available and loadable locally, and HTTP `503` otherwise.

## Deployment (Heroku)

```sh
# One-command deploy
./deploy.sh

# Or manually
heroku container:login
heroku container:push web --app story-maker-piper
heroku container:release web --app story-maker-piper
```

The container reads Heroku's runtime `PORT` environment variable automatically, so no Procfile command override is required.

Heroku dynos have an ephemeral filesystem. If the default voice is downloaded into `/models`, it will be lost on dyno restart or redeploy. For predictable boot-time readiness you have two options:

- extend the image/build process to bake the default voice into the image at build time
- allow on-demand downloads and accept that `/health` will stay `503` until the default voice exists locally

Useful checks after deploy:

```sh
heroku logs --tail --app story-maker-piper
curl https://story-maker-piper.herokuapp.com/health
```

The Rails app connects via the `PIPER_URL` env var (e.g. `https://story-maker-piper-abc123.herokuapp.com`).

## Environment Variables

### Server configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE` | `en_US-lessac-low` | Default voice model name |
| `DATA_DIR` | `/models` | Directory to search for `.onnx` voice files |
| `PORT` | `5000` | HTTP listen port |
| `PIPER_ALLOW_DOWNLOADS` | `true` | Enable `/download` endpoint |

### ONNX Runtime tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPER_MAX_LOADED_VOICES` | `0` | Max voice models cached in RAM (`0` = load fresh each request) |
| `PIPER_INTRA_OP_THREADS` | `1` | Threads within a single ONNX operator |
| `PIPER_INTER_OP_THREADS` | `1` | Threads across independent ONNX operators |
| `PIPER_EXECUTION_MODE` | `sequential` | `sequential` or `parallel` |
| `PIPER_ENABLE_CPU_MEM_ARENA` | `1` | Pre-allocate CPU memory arena |
| `PIPER_ENABLE_MEM_PATTERN` | `1` | Reuse memory allocation patterns |

### Resource control (set in Dockerfile)

| Variable | Default | Description |
|----------|---------|-------------|
| `MALLOC_ARENA_MAX` | `1` | Limits glibc malloc arenas (reduces RSS) |
| `OMP_NUM_THREADS` | `1` | Caps OpenMP threads |
| `OPENBLAS_NUM_THREADS` | `1` | Caps NumPy/OpenBLAS threads |
