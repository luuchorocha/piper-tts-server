from dataclasses import dataclass, field
from pathlib import Path

from src.core.constants import DEFAULT_SENTENCE_SILENCE


def _default_data_dirs() -> list[str]:
    return [str(Path.cwd() / ".data")]


@dataclass(frozen=True)
class AppDefaults:
    model: str = "en_US-lessac-medium"
    cuda: bool = False
    data_dir: list[str] = field(default_factory=_default_data_dirs)
    download_dir: str | None = None
    speaker: int | None = None
    sentence_silence: float = DEFAULT_SENTENCE_SILENCE
    length_scale: float | None = None
    noise_scale: float | None = None
    noise_w_scale: float | None = None
    max_loaded_voices: int = 0
    intra_op_threads: int = 1
    inter_op_threads: int = 1
    enable_cpu_mem_arena: bool = True
    enable_mem_pattern: bool = True
    allow_downloads: bool = True
    debug: bool = False


@dataclass(frozen=True)
class ServerDefaults:
    host: str = "0.0.0.0"
    port: int = 5000
    log_level: str = "warning"
    access_log: bool = False
    reload: bool = False
    workers: int = 1
    use_colors: bool = True
    limit_concurrency: int = 10
    timeout_keep_alive: int = 30


app_defaults = AppDefaults()
server_defaults = ServerDefaults()


__all__ = ["AppDefaults", "ServerDefaults", "app_defaults", "server_defaults"]
