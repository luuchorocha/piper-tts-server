import argparse
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.routes import build_routes
from src.cli.args import build_app_arg_parser, build_uvicorn_arg_parser
from src.core.context import AppContext
from src.core.session import build_session_options
from src.managers.voices.loader import resolve_model_path
from src.managers.voices.manager import VoiceManager

LOGGER = logging.getLogger(__name__)

def build_lifespan(context: AppContext):
    @asynccontextmanager
    async def lifespan(app: Starlette):
        try:
            yield
        finally:
            context.voice_manager.clear_cache()

    return lifespan


def create_app() -> Starlette:
    args, _ = build_app_arg_parser().parse_known_args()
    return create_app_from_args(args)


def create_app_from_args(args: argparse.Namespace) -> Starlette:
    setup_logging(args)
    data_dirs = [Path(data_dir) for data_dir in args.data_dir]
    download_dir = Path(args.download_dir) if args.download_dir else data_dirs[0]

    for data_dir in data_dirs:
        data_dir.mkdir(parents=True, exist_ok=True)

    download_dir.mkdir(parents=True, exist_ok=True)

    default_model_id = Path(args.model).name.removesuffix(".onnx")
    session_options = build_session_options(args)

    try:
        default_model_path: Optional[Path] = resolve_model_path(args.model, data_dirs)
    except ValueError:
        default_model_path = None

    voice_manager = VoiceManager(
        data_dirs=data_dirs,
        default_model_id=default_model_id,
        default_model_path=default_model_path,
        use_cuda=args.cuda,
        session_options=session_options,
        max_loaded_voices=args.max_loaded_voices,
        download_dir=download_dir,
        allow_downloads=args.allow_downloads,
    )
    context = AppContext(
        args=args,
        data_dirs=data_dirs,
        voice_manager=voice_manager,
        synthesis_semaphore=asyncio.Semaphore(1),
    )

    return Starlette(
        routes=build_routes(context),
        exception_handlers={500: server_error},
        lifespan=build_lifespan(context),
    )


def setup_logging(args: argparse.Namespace) -> None:
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

async def server_error(request: Request, exc: Exception) -> JSONResponse:
    client_host = request.client.host if request.client is not None else "unknown"
    LOGGER.exception(
        "Unhandled error during request %s %s client=%s",
        request.method,
        request.url.path,
        client_host,
    )
    return JSONResponse({"error": "Internal server error"}, status_code=500)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Piper TTS HTTP server",
        parents=[
            build_app_arg_parser(add_help=False),
            build_uvicorn_arg_parser(add_help=False),
        ],
    )
    args = parser.parse_args()
    app = create_app_from_args(args)

    uvicorn.run(
        app=app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=args.access_log,
        reload=args.reload,
        workers=args.workers,
        use_colors=args.use_colors,
        limit_concurrency=args.limit_concurrency,
        timeout_keep_alive=args.timeout_keep_alive,
    )
