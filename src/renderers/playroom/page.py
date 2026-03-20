import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from src.core.constants import (
    DEFAULT_LENGTH_SCALE,
    DEFAULT_NOISE_SCALE,
    DEFAULT_NOISE_W_SCALE,
    DEFAULT_NORMALIZE_AUDIO,
    DEFAULT_SENTENCE_SILENCE,
    DEFAULT_VOLUME,
)

_ASSET_DIR = Path(__file__).resolve().parent
_CONFIG_PLACEHOLDER = "__PLAYROOM_CONFIG__"
_SCRIPT_PLACEHOLDER = "__PLAYROOM_SCRIPT__"


@lru_cache(maxsize=None)
def _load_asset(name: str) -> str:
    return (_ASSET_DIR / name).read_text(encoding="utf-8")


def _serialize_config(config: dict[str, object]) -> str:
    return json.dumps(config).replace("<", "\\u003c")


def build_playroom_html(
    *,
    default_voice: str,
    speaker_id: Optional[int],
    length_scale: Optional[float],
    noise_scale: Optional[float],
    noise_w_scale: Optional[float],
    sentence_silence: float = DEFAULT_SENTENCE_SILENCE,
) -> str:
    config = {
        "default_voice": default_voice,
        "defaults": {
            "speaker_id": speaker_id,
            "sentence_silence": sentence_silence,
            "length_scale": (
                length_scale if length_scale is not None else DEFAULT_LENGTH_SCALE
            ),
            "noise_scale": (
                noise_scale if noise_scale is not None else DEFAULT_NOISE_SCALE
            ),
            "noise_w_scale": (
                noise_w_scale if noise_w_scale is not None else DEFAULT_NOISE_W_SCALE
            ),
            "volume": DEFAULT_VOLUME,
            "normalize_audio": DEFAULT_NORMALIZE_AUDIO,
        },
    }

    return (
        _load_asset("page.html")
        .replace(_CONFIG_PLACEHOLDER, _serialize_config(config))
        .replace(_SCRIPT_PLACEHOLDER, _load_asset("page.js"))
    )
