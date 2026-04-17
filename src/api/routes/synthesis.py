import asyncio
import base64
import logging
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.common.json_body import json_body_error_response, read_json
from src.core.context import AppContext, SynthesisOverloadedError
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


def build_synthesis_handler(
    context: AppContext,
    *,
    force_alignments: bool = False,
):
    async def synthesize(request: Request) -> Response:
        started_at = time.monotonic()

        try:
            data = await _read_request_data(request)
        except Exception as exc:
            return json_body_error_response(exc)

        if force_alignments:
            data = dict(data)
            data["include_alignments"] = True

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
            voice, lease_id, ephemeral = context.voice_manager.get(
                synthesis_request.requested_voice,
            )
            try:
                return synthesize_text(
                    voice=voice,
                    request_data=synthesis_request,
                    args=context.args,
                    alignment_engine=context.alignment_engine,
                    include_alignments=synthesis_request.include_alignments,
                )
            finally:
                context.voice_manager.release(voice, lease_id, ephemeral)

        try:
            async with context.synthesis_capacity.slot():
                result = await asyncio.to_thread(_do_synthesis)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except SynthesisOverloadedError as exc:
            elapsed = time.monotonic() - started_at
            LOGGER.warning(
                "[synthesize] overloaded voice=%s text_len=%d elapsed=%.3fs",
                synthesis_request.requested_voice,
                len(synthesis_request.text),
                elapsed,
            )
            return JSONResponse(
                {"error": str(exc)},
                status_code=503,
                headers={
                    "Retry-After": str(max(1, int(context.args.synthesis_acquire_timeout_seconds))),
                },
            )
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
                "alignment_mode": result.alignment_mode,
                "alignment_supported": result.alignment_supported,
                "alignment_error": result.alignment_error,
                "alignments": result.alignment.to_dict(),
            })

        return Response(result.wav_bytes, media_type="audio/wav")

    return synthesize
