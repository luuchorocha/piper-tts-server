from piper_http.core.context import AppContext
from starlette.requests import Request
from starlette.responses import JSONResponse


def build_health_handler(context: AppContext):
    def health(request: Request) -> JSONResponse:
        ready, error = context.voice_manager.probe_default_voice()
        payload = {
            "status": "ok" if ready else "error",
            "voice": context.voice_manager.default_model_id,
        }
        if error is not None:
            payload["error"] = error

        return JSONResponse(payload, status_code=200 if ready else 503)

    return health
