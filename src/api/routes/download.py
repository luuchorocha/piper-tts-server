import asyncio
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.common.json_body import json_body_error_response, read_json
from src.core.constants import VOICE_ID_RE
from src.core.context import AppContext
from src.managers.voices.manager import (
    VoiceDownloadBusyError,
    VoiceDownloadError,
    VoiceDownloadsDisabledError,
)
from src.parsers.common import parse_bool


async def _read_request_data(request: Request) -> dict[str, Any]:
    if request.method == "GET":
        return dict(request.query_params)

    return await read_json(request)


def build_download_handler(context: AppContext):
    async def download(request: Request) -> Response:
        try:
            data = await _read_request_data(request)
        except Exception as exc:
            return json_body_error_response(exc)

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
            force = parse_bool(
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
