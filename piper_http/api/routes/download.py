import asyncio
import json

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from piper_http.api.common.json_body import (
    BodyTooLarge,
    InvalidJSONPayload,
    read_json,
)
from piper_http.core.constants import VOICE_ID_RE
from piper_http.core.context import AppContext
from piper_http.managers.voices.manager import (
    VoiceDownloadBusyError,
    VoiceDownloadError,
    VoiceDownloadsDisabledError,
)


def _parse_bool_field(value, *, field_name: str, default: bool) -> bool:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

    raise ValueError(f"{field_name} must be a boolean")


def build_download_handler(context: AppContext):
    async def download(request: Request) -> Response:
        try:
            data = await read_json(request)
        except BodyTooLarge:
            return JSONResponse(
                {"error": "Request body exceeds 128 KB limit"},
                status_code=413,
            )
        except json.JSONDecodeError:
            return JSONResponse(
                {"error": "Invalid JSON in request body"},
                status_code=400,
            )
        except InvalidJSONPayload:
            return JSONResponse(
                {"error": "Request body must be a JSON object"},
                status_code=400,
            )

        model_id = data.get("voice")
        if not model_id:
            return JSONResponse({"error": "voice is required"}, status_code=400)
        if not isinstance(model_id, str):
            return JSONResponse({"error": "voice must be a string"}, status_code=400)
        if not VOICE_ID_RE.fullmatch(model_id):
            return JSONResponse(
                {"error": f"Invalid voice id: {model_id}"},
                status_code=400,
            )

        try:
            force = _parse_bool_field(
                data.get("force_redownload"),
                field_name="force_redownload",
                default=False,
            )
            await asyncio.to_thread(
                context.voice_manager.download,
                model_id,
                force_redownload=force,
                enforce_cooldown=True,
            )
            return Response(model_id, media_type="text/plain")
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except VoiceDownloadsDisabledError as exc:
            return JSONResponse({"error": str(exc)}, status_code=403)
        except VoiceDownloadBusyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=429)
        except VoiceDownloadError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    return download
