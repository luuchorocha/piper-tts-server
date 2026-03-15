import asyncio
import base64
import json
import logging
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.common.json_body import (
    BodyTooLarge,
    InvalidJSONPayload,
    read_json,
)
from src.core.context import AppContext
from src.parsers.synthesis.request import (
    RequestValidationError,
    SynthesisRequest,
)
from src.services.synthesis.service import SynthesisResult, synthesize_text

LOGGER = logging.getLogger(__name__)


async def _read_request_data(request: Request) -> dict[str, Any]:
    if request.method == "GET":
        return dict(request.query_params)

    return await read_json(request)


def build_synthesis_handler(context: AppContext):
    async def synthesize(request: Request) -> Response:
        started_at = time.monotonic()

        try:
            data = await _read_request_data(request)
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

        try:
            synthesis_request = SynthesisRequest.from_payload(
                data,
                default_voice=context.voice_manager.default_model_id,
                default_sentence_silence=context.args.sentence_silence,
                default_length_scale=context.args.length_scale,
                default_noise_scale=context.args.noise_scale,
                default_noise_w_scale=context.args.noise_w_scale,
            )
        except RequestValidationError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        def _do_synthesis() -> SynthesisResult:
            voice, ephemeral = context.voice_manager.get(synthesis_request.requested_voice)
            try:
                return synthesize_text(
                    voice=voice,
                    request_data=synthesis_request,
                    args=context.args,
                    include_alignments=synthesis_request.include_alignments,
                )
            finally:
                if ephemeral:
                    context.voice_manager.release_ephemeral(voice)

        try:
            async with context.synthesis_semaphore:
                result = await asyncio.to_thread(_do_synthesis)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except Exception:
            elapsed = time.monotonic() - started_at
            LOGGER.exception(
                "[synthesize] error voice=%s text_len=%d elapsed=%.3fs",
                synthesis_request.requested_voice,
                len(synthesis_request.text),
                elapsed,
            )
            raise

        # Return JSON with alignments if requested, raw WAV otherwise
        if synthesis_request.include_alignments and result.alignment:
            return JSONResponse({
                "audio_base64": base64.b64encode(result.wav_bytes).decode("ascii"),
                "sample_rate": result.sample_rate,
                "alignments": result.alignment.to_dict(),
            })

        return Response(result.wav_bytes, media_type="audio/wav")

    return synthesize
