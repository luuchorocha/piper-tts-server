import os
from dataclasses import dataclass, field
from pathlib import Path

from src.cli.env import env_bool, env_int
from src.core.constants import DEFAULT_SENTENCE_SILENCE


def _default_data_dirs() -> list[str]:
    raw_data_dir = os.getenv("DATA_DIR")
    if raw_data_dir is None:
        return [str(Path.cwd() / ".data")]

    return [path for path in raw_data_dir.split(os.pathsep) if path]


@dataclass(frozen=True)
class AppDefaults:
    model: str = os.getenv("VOICE", "en_US-lessac-medium")
    cuda: bool = False
    alignment_method: str = os.getenv("ALIGNMENT_METHOD", "silence")
    forced_aligner_bundle: str = os.getenv("FORCED_ALIGNER_BUNDLE", "WAV2VEC2_ASR_BASE_960H")
    forced_aligner_min_word_score: float = float(os.getenv("FORCED_ALIGNER_MIN_WORD_SCORE", "0.0"))
    data_dir: list[str] = field(default_factory=_default_data_dirs)
    download_dir: str | None = os.getenv("DOWNLOAD_DIR")
    speaker: int | None = None
    sentence_silence: float = DEFAULT_SENTENCE_SILENCE
    length_scale: float | None = None
    noise_scale: float | None = None
    noise_w_scale: float | None = None
    max_loaded_voices: int = env_int("PIPER_MAX_LOADED_VOICES", 1)
    intra_op_threads: int = env_int("PIPER_INTRA_OP_THREADS", 1)
    inter_op_threads: int = env_int("PIPER_INTER_OP_THREADS", 1)
    enable_cpu_mem_arena: bool = env_bool("PIPER_ENABLE_CPU_MEM_ARENA", True)
    enable_mem_pattern: bool = env_bool("PIPER_ENABLE_MEM_PATTERN", True)
    allow_downloads: bool = env_bool("PIPER_ALLOW_DOWNLOADS", True)
    debug: bool = env_bool("DEBUG", False)


@dataclass(frozen=True)
class ServerDefaults:
    host: str = "0.0.0.0"
    port: int = env_int("PORT", 5000)
    log_level: str = os.getenv("LOG_LEVEL", "warning")
    access_log: bool = env_bool("ACCESS_LOG", False)
    reload: bool = env_bool("RELOAD", False)
    workers: int = env_int("WEB_CONCURRENCY", 1)
    use_colors: bool = env_bool("USE_COLORS", True)
    limit_concurrency: int = env_int("LIMIT_CONCURRENCY", 10)
    timeout_keep_alive: int = env_int("TIMEOUT_KEEP_ALIVE", 30)
    synthesis_concurrency: int = env_int("SYNTHESIS_CONCURRENCY", 1)
    synthesis_acquire_timeout_seconds: float = float(os.getenv("SYNTHESIS_ACQUIRE_TIMEOUT_SECONDS", "5"))
    max_waiting_synthesis_requests: int = env_int("MAX_WAITING_SYNTHESIS_REQUESTS", 2)


app_defaults = AppDefaults()
server_defaults = ServerDefaults()


__all__ = ["AppDefaults", "ServerDefaults", "app_defaults", "server_defaults"]
