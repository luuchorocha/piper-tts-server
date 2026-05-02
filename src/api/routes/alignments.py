import asyncio
import logging
import time

from starlette.formparsers import MultiPartException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from src.core.context import AppContext, SynthesisOverloadedError
from src.parsers.alignments import AudioUploadTooLarge, parse_uploaded_alignment_request
from src.parsers.synthesis.request import RequestValidationError
from src.renderers.alignments.page import build_alignments_html
from src.services.alignments import UploadedAlignmentResult, align_uploaded_wav

LOGGER = logging.getLogger(__name__)


def _is_multipart(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "multipart/form-data"


def _alignment_response(result: UploadedAlignmentResult) -> JSONResponse:
    return JSONResponse({
        "sample_rate": result.sample_rate,
        "alignment_mode": result.alignment_mode,
        "alignment_supported": result.alignment_supported,
        "alignment_error": result.alignment_error,
        "alignments": result.alignment.to_dict(),
    })


def build_alignments_handler(context: AppContext):
    async def align(request: Request) -> Response:
        if request.method == "GET":
            return HTMLResponse(build_alignments_html())

        started_at = time.monotonic()

        if not _is_multipart(request):
            return JSONResponse(
                {"error": "Content-Type must be multipart/form-data"},
                status_code=400,
            )

        try:
            form = await request.form()
            alignment_request = await parse_uploaded_alignment_request(form)
        except AudioUploadTooLarge as exc:
            return JSONResponse({"error": str(exc)}, status_code=413)
        except (MultiPartException, RequestValidationError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        try:
            async with context.synthesis_capacity.slot():
                result = await asyncio.to_thread(
                    align_uploaded_wav,
                    request_data=alignment_request,
                    alignment_engine=context.alignment_engine,
                )
        except RequestValidationError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except SynthesisOverloadedError as exc:
            elapsed = time.monotonic() - started_at
            LOGGER.warning(
                "[alignments] overloaded text_len=%d elapsed=%.3fs",
                len(alignment_request.text),
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
                "[alignments] error text_len=%d elapsed=%.3fs",
                len(alignment_request.text),
                elapsed,
            )
            raise

        return _alignment_response(result)

    return align
