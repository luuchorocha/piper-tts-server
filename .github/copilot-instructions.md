# Copilot instructions for piper-tts-server

## Commands

- Set up local dependencies: `./bin/env`
- Run the development server: `./bin/dev -m en_US-lessac-low --data-dir . --port 5000 --debug`
- Run the server without the dev banner: `./bin/web -m en_US-lessac-low --data-dir . --port 5000 --debug`
- Run all tests: `python3 -m unittest discover -s tests`
- Run one test module: `python3 -m unittest tests.test_synthesis_route`
- Run one test method: `python3 -m unittest tests.test_synthesis_route.SynthesisRouteTest.test_timestamps_route_returns_alignment_mode_and_forces_alignments`
- Build the production image: `docker build -t piper-tts .`
- Verify a running server: `curl http://localhost:5000/health`

## Architecture

This is a Python 3.11 Starlette + Uvicorn HTTP API around Piper TTS. `main.py` is only a thin entrypoint; application construction lives in `src/app.py`, where CLI/env defaults are parsed, `AppContext` is assembled, and route factories from `src/api/routes/` are wired into the Starlette app.

Request handling is intentionally split by layer:

- `src/api/routes/` owns HTTP concerns: reading JSON/query payloads, mapping validation/runtime errors to status codes, and returning either raw `audio/wav` or timestamp JSON.
- `src/parsers/synthesis/request.py` owns synthesis payload validation and default resolution for request fields.
- `src/services/synthesis/service.py` owns the blocking Piper synthesis call, WAV assembly, speaker/scale resolution, optional inter-sentence silence, and alignment fallback selection.
- `src/managers/voices/` owns voice model resolution, on-demand downloads, readiness probing, and thread-safe loaded-voice caching/refcounting.
- `src/services/alignment/` owns timestamp generation. Piper-native phoneme timing is attempted first when available, then the configured external alignment engine is used (`forced_ctc` by default, `silence` via `ALIGNMENT_METHOD=silence`).

The app uses async route handlers but moves blocking Piper, ONNX, filesystem, and download work into `asyncio.to_thread(...)`. Synthesis admission is controlled separately by `SynthesisCapacity` in `src/core/context.py`; keep this capacity gate around synthesis work so concurrent requests do not overload the process.

Voice models are runtime assets, not repository or image contents. The server searches one or more `--data-dir` directories for `<voice>.onnx` plus `<voice>.onnx.json`; `/download` can fetch models into `--download-dir` when downloads are enabled.

## Codebase conventions

- Route modules expose `build_*_handler(context)` factories and close over `AppContext` instead of using global application state.
- GET and POST synthesis/download endpoints share handlers: GET reads query params, POST reads a JSON object through `src/api/common/json_body.py`, which enforces the 128 KB body limit.
- Public request validation errors are raised as `RequestValidationError` from parser code and translated to `{"error": ...}` responses in route code.
- Voice ids must match `VOICE_ID_RE` from `src/core/constants.py`; keep new voice-related inputs on that same validation path.
- Voice cache changes must preserve the `VoiceManager.get(...)` / `release(...)` lease contract so cached ONNX sessions are not freed while in use.
- `requirements.txt` is the production dependency source and is copied directly into the Docker build; keep dependency changes compatible with the Dockerfile install path.
- Tests use `unittest` with lightweight fakes/mocks rather than requiring real Piper voice models for unit coverage.
