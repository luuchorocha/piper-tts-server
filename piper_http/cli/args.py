import argparse
import os
from pathlib import Path

from piper_http.cli.env import env_bool, env_int


def _non_negative_int(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return n


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return n


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Piper TTS HTTP server")
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Bind address",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=env_int("PORT", 5000),
        help="Bind port",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=(
            os.getenv("VOICE")
            if os.getenv("VOICE") is not None
            else "en_US-lessac-low"
        ),
        help="Default voice model path or id (env: VOICE)",
    )
    parser.add_argument("-s", "--speaker", type=int, help="Default speaker id")
    parser.add_argument("--length-scale", "--length_scale", type=float)
    parser.add_argument("--noise-scale", "--noise_scale", type=float)
    parser.add_argument(
        "--noise-w-scale",
        "--noise_w_scale",
        "--noise-w",
        "--noise_w",
        type=float,
    )
    parser.add_argument(
        "--cuda",
        action="store_true",
        default=env_bool("PIPER_USE_CUDA", False),
        help="Use CUDA for inference",
    )
    parser.add_argument(
        "--sentence-silence",
        "--sentence_silence",
        type=float,
        default=0.0,
    )

    data_dir_default = os.getenv("DATA_DIR")
    parser.add_argument(
        "--data-dir",
        "--data_dir",
        action="append",
        default=[data_dir_default] if data_dir_default else [str(Path.cwd())],
        help="Directories to search for voice models (env: DATA_DIR)",
    )
    parser.add_argument(
        "--download-dir",
        "--download_dir",
        default=os.getenv("DOWNLOAD_DIR") or data_dir_default,
        help="Directory to download voices into (env: DOWNLOAD_DIR or DATA_DIR)",
    )
    parser.add_argument(
        "--max-loaded-voices",
        "--max_loaded_voices",
        type=_non_negative_int,
        default=env_int("PIPER_MAX_LOADED_VOICES", 0),
        help="Max cached models in memory (0 = no cache, load fresh each time)",
    )
    parser.add_argument(
        "--intra-op-threads",
        "--intra_op_threads",
        type=_positive_int,
        default=env_int("PIPER_INTRA_OP_THREADS", 1),
    )
    parser.add_argument(
        "--inter-op-threads",
        "--inter_op_threads",
        type=_positive_int,
        default=env_int("PIPER_INTER_OP_THREADS", 1),
    )
    parser.add_argument(
        "--execution-mode",
        "--execution_mode",
        choices=["sequential", "parallel"],
        default=os.getenv("PIPER_EXECUTION_MODE", "sequential"),
    )
    parser.add_argument(
        "--enable-cpu-mem-arena",
        "--enable_cpu_mem_arena",
        action=argparse.BooleanOptionalAction,
        default=env_bool("PIPER_ENABLE_CPU_MEM_ARENA", True),
    )
    parser.add_argument(
        "--enable-mem-pattern",
        "--enable_mem_pattern",
        action=argparse.BooleanOptionalAction,
        default=env_bool("PIPER_ENABLE_MEM_PATTERN", True),
    )
    parser.add_argument(
        "--allow-downloads",
        "--allow_downloads",
        action=argparse.BooleanOptionalAction,
        default=env_bool("PIPER_ALLOW_DOWNLOADS", True),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=env_bool("PIPER_DEBUG", False),
        help="Enable debug logging and ONNX profiling",
    )

    return parser
