from dataclasses import dataclass
from typing import Any, Mapping, Optional

from piper_http.core.constants import (
    DEFAULT_LENGTH_SCALE,
    DEFAULT_NOISE_SCALE,
    DEFAULT_NOISE_W_SCALE,
    DEFAULT_NORMALIZE_AUDIO,
    DEFAULT_SENTENCE_SILENCE,
    DEFAULT_VOLUME,
    MAX_TEXT_LENGTH,
    VOICE_ID_RE,
)


class RequestValidationError(ValueError):
    pass


def parse_optional_int(value: Any, *, field_name: str) -> Optional[int]:
    if value is None or value == "":
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RequestValidationError(
            f"{field_name} must be an integer",
        ) from exc

    if parsed < 0:
        raise RequestValidationError(f"{field_name} must be >= 0")

    return parsed


def parse_float(
    value: Any,
    *,
    field_name: str,
    default: float,
    min_value: Optional[float] = None,
) -> float:
    if value is None or value == "":
        parsed = default
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise RequestValidationError(
                f"{field_name} must be a number",
            ) from exc

    if min_value is not None and parsed < min_value:
        raise RequestValidationError(f"{field_name} must be >= {min_value}")

    return parsed


def parse_bool(value: Any, *, field_name: str, default: bool) -> bool:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

    raise RequestValidationError(f"{field_name} must be a boolean")


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    requested_voice: str
    speaker_id: Optional[int]
    speaker: Optional[str]
    sentence_silence: float
    length_scale: float
    noise_scale: float
    noise_w_scale: float
    normalize_audio: bool
    volume: float
    include_alignments: bool
    has_length_scale: bool
    has_noise_scale: bool
    has_noise_w_scale: bool

    @classmethod
    def from_payload(
        cls,
        data: Mapping[str, Any],
        *,
        default_voice: str,
        default_sentence_silence: float,
        default_length_scale: Optional[float],
        default_noise_scale: Optional[float],
        default_noise_w_scale: Optional[float],
    ) -> "SynthesisRequest":
        raw_text = data.get("text", "")
        if not isinstance(raw_text, str):
            raise RequestValidationError("text must be a string")

        text = raw_text.strip()
        if not text:
            raise RequestValidationError("No text provided")
        if len(text) > MAX_TEXT_LENGTH:
            raise RequestValidationError(
                f"Text exceeds maximum length of {MAX_TEXT_LENGTH} characters",
            )

        requested_voice = data.get("voice", default_voice)
        if requested_voice in ("", None):
            requested_voice = default_voice
        elif not isinstance(requested_voice, str):
            raise RequestValidationError("voice must be a string")

        if requested_voice and not VOICE_ID_RE.fullmatch(requested_voice):
            raise RequestValidationError(f"Invalid voice id: {requested_voice}")

        raw_speaker = data.get("speaker")
        if raw_speaker is not None and not isinstance(raw_speaker, str):
            raise RequestValidationError("speaker must be a string")
        speaker = raw_speaker.strip() if isinstance(raw_speaker, str) else None
        if speaker == "":
            speaker = None

        return cls(
            text=text,
            requested_voice=requested_voice,
            speaker_id=parse_optional_int(data.get("speaker_id"), field_name="speaker_id"),
            speaker=speaker,
            sentence_silence=parse_float(
                data.get("sentence_silence"),
                field_name="sentence_silence",
                default=default_sentence_silence,
                min_value=0.0,
            ),
            length_scale=parse_float(
                data.get("length_scale"),
                field_name="length_scale",
                default=(
                    default_length_scale
                    if default_length_scale is not None
                    else DEFAULT_LENGTH_SCALE
                ),
            ),
            noise_scale=parse_float(
                data.get("noise_scale"),
                field_name="noise_scale",
                default=(
                    default_noise_scale
                    if default_noise_scale is not None
                    else DEFAULT_NOISE_SCALE
                ),
            ),
            noise_w_scale=parse_float(
                data.get("noise_w_scale"),
                field_name="noise_w_scale",
                default=(
                    default_noise_w_scale
                    if default_noise_w_scale is not None
                    else DEFAULT_NOISE_W_SCALE
                ),
            ),
            normalize_audio=parse_bool(
                data.get("normalize_audio"),
                field_name="normalize_audio",
                default=DEFAULT_NORMALIZE_AUDIO,
            ),
            volume=parse_float(
                data.get("volume"),
                field_name="volume",
                default=DEFAULT_VOLUME,
            ),
            include_alignments=parse_bool(
                data.get("include_alignments"),
                field_name="include_alignments",
                default=False,
            ),
            has_length_scale=(
                "length_scale" in data and data.get("length_scale") not in ("", None)
            ),
            has_noise_scale=(
                "noise_scale" in data and data.get("noise_scale") not in ("", None)
            ),
            has_noise_w_scale=(
                "noise_w_scale" in data and data.get("noise_w_scale") not in ("", None)
            ),
        )
