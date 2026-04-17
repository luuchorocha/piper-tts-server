import asyncio

from src.core.context import AppContext
from starlette.requests import Request
from starlette.responses import JSONResponse


def build_health_handler(context: AppContext):
    async def health(request: Request) -> JSONResponse:
        ready, error = await asyncio.to_thread(
            context.voice_manager.probe_default_voice,
        )
        capacity = await context.synthesis_capacity.snapshot()
        overloaded = capacity.overloaded or (capacity.in_flight >= capacity.limit and capacity.waiting > 0)

        payload = {
            "status": "ok" if ready and not overloaded else ("overloaded" if overloaded else "error"),
            "voice": context.voice_manager.default_model_id,
            "synthesis": {
                "limit": capacity.limit,
                "in_flight": capacity.in_flight,
                "waiting": capacity.waiting,
                "max_waiting": capacity.max_waiters,
                "acquire_timeout_seconds": capacity.acquire_timeout_seconds,
            },
        }
        if error is not None:
            payload["error"] = error

        return JSONResponse(payload, status_code=200 if ready and not overloaded else 503)

    return health
