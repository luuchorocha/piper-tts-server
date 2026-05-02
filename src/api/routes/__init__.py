from starlette.routing import Route

from src.api.routes.alignments import build_alignments_handler
from src.api.routes.docs import openapi_json, swagger_ui
from src.api.routes.download import build_download_handler
from src.api.routes.health import build_health_handler
from src.api.routes.playroom import build_playroom_handler
from src.api.routes.synthesis import build_synthesis_handler
from src.api.routes.voices import build_all_voices_handler, build_voices_handler
from src.core.context import AppContext


def build_routes(context: AppContext) -> list[Route]:
    return [
        Route("/docs", swagger_ui, methods=["GET"]),
        Route("/openapi.json", openapi_json, methods=["GET"]),
        Route("/", build_synthesis_handler(context), methods=["GET", "POST"]),
        Route(
            "/timestamps",
            build_synthesis_handler(context, force_alignments=True),
            methods=["GET", "POST"],
        ),
        Route("/alignments", build_alignments_handler(context), methods=["POST"]),
        Route("/health", build_health_handler(context), methods=["GET"]),
        Route("/voices", build_voices_handler(context), methods=["GET"]),
        Route("/all-voices", build_all_voices_handler(), methods=["GET"]),
        Route("/playroom", build_playroom_handler(context), methods=["GET"]),
        Route("/download", build_download_handler(context), methods=["GET", "POST"]),
    ]
