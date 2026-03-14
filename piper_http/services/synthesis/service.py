import argparse
import io
import logging
import wave
from dataclasses import dataclass
from typing import Optional

from piper import PiperVoice, SynthesisConfig

from piper_http.parsers.synthesis.request import SynthesisRequest
from piper_http.services.alignment import (
    AlignmentResult,
    group_phonemes_into_words,
    phoneme_alignments_to_timestamps,
)

LOGGER = logging.getLogger(__name__)


def _resolve_speaker_id(
    *,
    voice: PiperVoice,
    request_data: SynthesisRequest,
    default_speaker_id: int | None,
) -> int | None:
    speaker_id = request_data.speaker_id

    if voice.config.num_speakers > 1 and speaker_id is None:
        if request_data.speaker:
            speaker_id = voice.config.speaker_id_map.get(request_data.speaker)
            if speaker_id is None:
                LOGGER.warning(
                    "Speaker not found: '%s' in %s",
                    request_data.speaker,
                    voice.config.speaker_id_map.keys(),
                )

        if speaker_id is None:
            speaker_id = default_speaker_id or 0

    if speaker_id is not None and speaker_id >= voice.config.num_speakers:
        return 0

    return speaker_id


def _resolve_scale(
    *,
    request_value: float,
    has_request_value: bool,
    default_value: float | None,
    voice_value: float,
) -> float:
    if has_request_value:
        return request_value

    if default_value is not None:
        return default_value

    return voice_value


@dataclass
class SynthesisResult:
    """Result of synthesis, optionally including alignment data."""

    wav_bytes: bytes
    sample_rate: int
    alignment: Optional[AlignmentResult] = None


def synthesize_text(
    *,
    voice: PiperVoice,
    request_data: SynthesisRequest,
    args: argparse.Namespace,
    include_alignments: bool = False,
) -> SynthesisResult:
    speaker_id = _resolve_speaker_id(
        voice=voice,
        request_data=request_data,
        default_speaker_id=args.speaker,
    )

    synthesis_config = SynthesisConfig(
        speaker_id=speaker_id,
        length_scale=_resolve_scale(
            request_value=request_data.length_scale,
            has_request_value=request_data.has_length_scale,
            default_value=args.length_scale,
            voice_value=voice.config.length_scale,
        ),
        noise_scale=_resolve_scale(
            request_value=request_data.noise_scale,
            has_request_value=request_data.has_noise_scale,
            default_value=args.noise_scale,
            voice_value=voice.config.noise_scale,
        ),
        noise_w_scale=_resolve_scale(
            request_value=request_data.noise_w_scale,
            has_request_value=request_data.has_noise_w_scale,
            default_value=args.noise_w_scale,
            voice_value=voice.config.noise_w_scale,
        ),
        normalize_audio=request_data.normalize_audio,
        volume=request_data.volume,
    )

    LOGGER.debug("Synthesizing: '%s' config=%s", request_data.text[:80], synthesis_config)

    buffer = io.BytesIO()
    sample_rate = 22050  # will be updated from first chunk
    all_phoneme_timestamps = []
    time_offset = 0.0

    with wave.open(buffer, "wb") as wav_file:
        params_set = False
        for index, chunk in enumerate(
            voice.synthesize(
                request_data.text,
                synthesis_config,
                include_alignments=include_alignments,
            )
        ):
            if not params_set:
                wav_file.setframerate(chunk.sample_rate)
                wav_file.setsampwidth(chunk.sample_width)
                wav_file.setnchannels(chunk.sample_channels)
                sample_rate = chunk.sample_rate
                params_set = True

            # Add silence between sentences
            if index > 0:
                silence_samples = int(
                    chunk.sample_rate
                    * request_data.sentence_silence
                    * chunk.sample_width
                    * chunk.sample_channels
                )
                wav_file.writeframes(bytes(silence_samples))
                time_offset += request_data.sentence_silence

            wav_file.writeframes(chunk.audio_int16_bytes)

            # Collect alignment data if requested
            if include_alignments and chunk.phoneme_alignments:
                chunk_phonemes = phoneme_alignments_to_timestamps(
                    chunk.phoneme_alignments,
                    sample_rate,
                    time_offset,
                )
                all_phoneme_timestamps.extend(chunk_phonemes)

            # Update time offset for next chunk
            chunk_duration = len(chunk.audio_int16_bytes) / (
                chunk.sample_rate * chunk.sample_width * chunk.sample_channels
            )
            time_offset += chunk_duration

    wav_bytes = buffer.getvalue()

    # Build alignment result if requested
    alignment = None
    if include_alignments:
        alignment = AlignmentResult(
            phonemes=all_phoneme_timestamps,
            words=group_phonemes_into_words(request_data.text, all_phoneme_timestamps),
            sample_rate=sample_rate,
        )

    return SynthesisResult(
        wav_bytes=wav_bytes,
        sample_rate=sample_rate,
        alignment=alignment,
    )
