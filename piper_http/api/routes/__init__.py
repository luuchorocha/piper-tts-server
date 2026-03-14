from starlette.routing import Route

from piper_http.api.routes.download import build_download_handler
from piper_http.api.routes.health import build_health_handler
from piper_http.api.routes.playroom import build_playroom_handler
from piper_http.api.routes.synthesis import build_synthesis_handler
from piper_http.api.routes.voices import build_all_voices_handler, build_voices_handler
from piper_http.core.context import AppContext


def build_routes(context: AppContext) -> list[Route]:
    return [
        Route("/", build_synthesis_handler(context), methods=["GET", "POST"]),
        Route("/health", build_health_handler(context), methods=["GET"]),
        Route("/voices", build_voices_handler(context), methods=["GET"]),
        Route("/all-voices", build_all_voices_handler(), methods=["GET"]),
        Route("/playroom", build_playroom_handler(context), methods=["GET"]),
        Route("/download", build_download_handler(context), methods=["POST"]),
    ]
