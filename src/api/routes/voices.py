import asyncio
import json
import logging
import time
from pathlib import Path
from urllib.request import urlopen

from piper.download_voices import VOICES_JSON
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.core.constants import ALL_VOICES_CACHE_TTL_SECS
from src.core.context import AppContext

LOGGER = logging.getLogger(__name__)


def _iter_config_paths(context: AppContext):
    if context.voice_manager.default_model_path:
        yield Path(f"{context.voice_manager.default_model_path}.json")

    for data_dir in context.data_dirs:
        for onnx_file in data_dir.glob("*.onnx"):
            config_path = Path(f"{onnx_file}.json")
            if config_path.exists():
                yield config_path


def _load_local_voices(context: AppContext) -> dict[str, dict]:
    voices: dict[str, dict] = {}

    for config_path in _iter_config_paths(context):
        model_id = config_path.name.removesuffix(".onnx.json")
        if model_id in voices:
            continue

        with open(config_path, "r", encoding="utf-8") as handle:
            voices[model_id] = json.load(handle)

    return voices


class AllVoicesCatalog:
    def __init__(self, ttl_secs: float = ALL_VOICES_CACHE_TTL_SECS) -> None:
        self.ttl_secs = ttl_secs
        self._payload: dict | None = None
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return (
            self._payload is not None
            and (time.monotonic() - self._fetched_at) < self.ttl_secs
        )

    @staticmethod
    def _fetch() -> dict:
        with urlopen(VOICES_JSON) as response:
            return json.load(response)

    async def get(self) -> dict:
        if self._is_fresh():
            return self._payload

        async with self._lock:
            if self._is_fresh():
                return self._payload

            payload = await asyncio.to_thread(self._fetch)
            self._payload = payload
            self._fetched_at = time.monotonic()
            return payload


def build_voices_handler(context: AppContext):
    def voices(request: Request) -> JSONResponse:
        return JSONResponse(_load_local_voices(context))

    return voices


def build_all_voices_handler():
    catalog = AllVoicesCatalog()

    async def all_voices(request: Request) -> JSONResponse:
        try:
            payload = await catalog.get()
        except Exception:
            LOGGER.exception("Failed to fetch all voices list")
            return JSONResponse(
                {"error": "Failed to fetch voices list"},
                status_code=500,
            )

        return JSONResponse(
            payload,
            status_code=200,
            media_type="application/json",
            headers={"Cache-Control": f"public, max-age={int(catalog.ttl_secs)}"},
        )

    return all_voices
