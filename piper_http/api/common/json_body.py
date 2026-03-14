import json
from typing import Any

from starlette.requests import Request

from piper_http.core.constants import MAX_BODY_BYTES


class BodyTooLarge(Exception):
    pass


class InvalidJSONPayload(Exception):
    pass


async def read_json(request: Request) -> dict[str, Any]:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise BodyTooLarge()

    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise InvalidJSONPayload()

    return payload
