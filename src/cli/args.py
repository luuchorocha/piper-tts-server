import argparse
from argparse import ArgumentParser

from src.cli.defaults import app_defaults, server_defaults


def build_app_arg_parser(*, add_help: bool = True) -> ArgumentParser:
    parser = ArgumentParser(description="Piper TTS Engine", add_help=add_help)

    parser.add_argument(
        "-m",
        "--model",
        default=app_defaults.model,
        help="Path to an ONNX model file or voice id",
    )
    parser.add_argument("-s", "--speaker", type=int, default=app_defaults.speaker)
    parser.add_argument(
        "--length-scale",
        "--length_scale",
        dest="length_scale",
        type=float,
        default=app_defaults.length_scale,
    )
    parser.add_argument(
        "--noise-scale",
        "--noise_scale",
        dest="noise_scale",
        type=float,
        default=app_defaults.noise_scale,
    )
    parser.add_argument(
        "--noise-w-scale",
        "--noise_w_scale",
        "--noise-w",
        "--noise_w",
        dest="noise_w_scale",
        type=float,
        default=app_defaults.noise_w_scale,
    )
    parser.add_argument("--cuda", action=argparse.BooleanOptionalAction, default=app_defaults.cuda)
    parser.add_argument(
        "--sentence-silence",
        "--sentence_silence",
        dest="sentence_silence",
        type=float,
        default=app_defaults.sentence_silence,
    )
    parser.add_argument(
        "--data-dir",
        "--data_dir",
        dest="data_dir",
        action="append",
        default=list(app_defaults.data_dir),
        help="Directory to scan for voices. Can be provided multiple times.",
    )
    parser.add_argument(
        "--download-dir",
        "--download_dir",
        dest="download_dir",
        default=app_defaults.download_dir,
    )
    parser.add_argument(
        "--max-loaded-voices",
        type=int,
        default=app_defaults.max_loaded_voices,
    )
    parser.add_argument(
        "--intra-op-threads",
        type=int,
        default=app_defaults.intra_op_threads,
    )
    parser.add_argument(
        "--inter-op-threads",
        type=int,
        default=app_defaults.inter_op_threads,
    )
    parser.add_argument(
        "--enable-cpu-mem-arena",
        action=argparse.BooleanOptionalAction,
        default=app_defaults.enable_cpu_mem_arena,
    )
    parser.add_argument(
        "--enable-mem-pattern",
        action=argparse.BooleanOptionalAction,
        default=app_defaults.enable_mem_pattern,
    )
    parser.add_argument(
        "--allow-downloads",
        action=argparse.BooleanOptionalAction,
        default=app_defaults.allow_downloads,
    )
    parser.add_argument("--debug", action=argparse.BooleanOptionalAction, default=app_defaults.debug)

    return parser


def build_uvicorn_arg_parser(*, add_help: bool = True) -> ArgumentParser:
    parser = ArgumentParser(description="Piper TTS Uvicorn server", add_help=add_help)

    parser.add_argument("--host", default=server_defaults.host)
    parser.add_argument("--port", type=int, default=server_defaults.port)
    parser.add_argument("--log-level", default=server_defaults.log_level)
    parser.add_argument(
        "--access-log",
        action=argparse.BooleanOptionalAction,
        default=server_defaults.access_log,
    )
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=server_defaults.reload)
    parser.add_argument("--workers", type=int, default=server_defaults.workers)
    parser.add_argument(
        "--use-colors",
        action=argparse.BooleanOptionalAction,
        default=server_defaults.use_colors,
    )
    parser.add_argument(
        "--limit-concurrency",
        type=int,
        default=server_defaults.limit_concurrency,
    )
    parser.add_argument(
        "--timeout-keep-alive",
        type=int,
        default=server_defaults.timeout_keep_alive,
    )

    return parser


def app_arg_parser(*, add_help: bool = True) -> ArgumentParser:
    return build_app_arg_parser(add_help=add_help)


def uvicorn_arg_parser(*, add_help: bool = True) -> ArgumentParser:
    return build_uvicorn_arg_parser(add_help=add_help)


build_uvicon_arg_parser = build_uvicorn_arg_parser


__all__ = [
    "app_arg_parser",
    "uvicorn_arg_parser",
    "build_app_arg_parser",
    "build_uvicorn_arg_parser",
    "build_uvicon_arg_parser",
]
