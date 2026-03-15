import argparse
import os
from pathlib import Path
import os

app_defaults: dict = {
    "data_dir": str(Path.cwd().joinpath(".data")),
    "max_loaded_voices": 0,
    "intra_op_threads": 1,
    "inter_op_threads": 1,
    "execution_mode": "sequential",
    "enable_cpu_mem_arena": True,
    "enable_mem_pattern": True,
    "allow_downloads": True,
}

server_defaults = {
    "host": "",
    "port": 5000,
    "log_level": "warning",
    "access_log": False,
    "reload": False,
    "workers": 1,
    "use_colors": True,
    "limit_concurrency": 10,
    "timeout_keep_alive": 30,
}

def build_app_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Piper TTS Engine")
    parser.add_argument(
        "--cuda",
        default=False,
    )
    parser.add_argument(
        "--data-dir",
        default=app_defaults.get('data_dir')
    )
    parser.add_argument(
        "--max-loaded-voices",
        default=app_defaults.get('max_loaded_voices')
    )
    parser.add_argument(
        "--intra-op-threads",
    )
    parser.add_argument(
        "--inter-op-threads",
    )
    parser.add_argument(
        "--execution-mode",
    )
    parser.add_argument(
        "--enable-cpu-mem-arena",
    )
    parser.add_argument(
        "--enable-mem-pattern",
    )
    parser.add_argument(
        "--allow-downloads",
    )
    parser.add_argument(
        "--debug",
    )

    return parser

def build_uvicon_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Piper TTS Uvicorn server")
    parser.add_argument(
        "--host",
    )
    parser.add_argument(
        "--port",
    )

    return parser
