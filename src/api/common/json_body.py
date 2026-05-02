import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from src.core.constants import MAX_BODY_BYTES


class BodyTooLarge(Exception):
    pass


class InvalidJSONPayload(Exception):
    pass


def json_body_error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, BodyTooLarge):
        return JSONResponse(
            {"error": "Request body exceeds 128 KB limit"},
            status_code=413,
        )

    if isinstance(exc, json.JSONDecodeError):
        return JSONResponse(
            {"error": "Invalid JSON in request body"},
            status_code=400,
        )

    if isinstance(exc, InvalidJSONPayload):
        return JSONResponse(
            {"error": "Request body must be a JSON object"},
            status_code=400,
        )

    raise TypeError(f"Unsupported JSON body exception: {type(exc).__name__}")


async def read_json(request: Request) -> dict[str, Any]:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise BodyTooLarge()

    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise InvalidJSONPayload()

    return payload
