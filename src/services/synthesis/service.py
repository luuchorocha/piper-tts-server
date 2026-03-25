import argparse
import io
import logging
import wave
from dataclasses import dataclass
from typing import Callable, Optional

from piper import PiperVoice, SynthesisConfig

from src.parsers.synthesis.request import SynthesisRequest
from src.services.alignment import (
    AlignmentResult,
    AlignmentError,
    AlignmentEngine,
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
    alignment_supported: bool = True
    alignment_error: Optional[str] = None
    alignment_mode: Optional[str] = None


def synthesize_text(
    *,
    voice: PiperVoice,
    request_data: SynthesisRequest,
    args: argparse.Namespace,
    alignment_engine: AlignmentEngine,
    include_alignments: bool = False,
    on_synthesis_complete: Optional[Callable[[], None]] = None,
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
    time_offset = 0.0
    sample_channels = 1
    sample_width = 2

    with wave.open(buffer, "wb") as wav_file:
        params_set = False
        for index, chunk in enumerate(
            voice.synthesize(
                request_data.text,
                synthesis_config,
                include_alignments=False,
            )
        ):
            if not params_set:
                wav_file.setframerate(chunk.sample_rate)
                wav_file.setsampwidth(chunk.sample_width)
                wav_file.setnchannels(chunk.sample_channels)
                sample_rate = chunk.sample_rate
                sample_channels = chunk.sample_channels
                sample_width = chunk.sample_width
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

            # Update time offset for next chunk
            chunk_duration = len(chunk.audio_int16_bytes) / (
                chunk.sample_rate * chunk.sample_width * chunk.sample_channels
            )
            time_offset += chunk_duration

    wav_bytes = buffer.getvalue()
    buffer.close()

    # Notify caller that synthesis is done — voice model can be offloaded
    # before the alignment model is loaded.
    if on_synthesis_complete is not None:
        on_synthesis_complete()

    # Build alignment result if requested
    alignment = None
    alignment_supported = True
    alignment_error: Optional[str] = None
    alignment_mode: Optional[str] = None
    if include_alignments:
        alignment_mode = alignment_engine.mode
        if sample_width != 2:
            alignment_supported = False
            alignment_error = "Alignment engine supports 16-bit PCM audio only"
            alignment = AlignmentResult(sample_rate=sample_rate)
        else:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wav_reader:
                pcm_bytes = wav_reader.readframes(wav_reader.getnframes())

            try:
                alignment = alignment_engine.align(
                    text=request_data.text,
                    grammar=request_data.grammar,
                    pcm_bytes=pcm_bytes,
                    sample_rate=sample_rate,
                    channels=sample_channels,
                )
            except AlignmentError as exc:
                alignment_supported = False
                alignment_error = str(exc)
                alignment = AlignmentResult(sample_rate=sample_rate)

            if alignment_supported and not alignment.words:
                alignment_supported = False
                alignment_error = "Alignment engine returned no words"

    return SynthesisResult(
        wav_bytes=wav_bytes,
        sample_rate=sample_rate,
        alignment=alignment,
        alignment_supported=(alignment_supported and bool(alignment and alignment.words or not include_alignments)),
        alignment_error=alignment_error,
        alignment_mode=alignment_mode,
    )
