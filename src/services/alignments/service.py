from dataclasses import dataclass
from typing import Optional

from src.parsers.alignments import UploadedAlignmentRequest
from src.parsers.synthesis.request import RequestValidationError
from src.services.alignment import AlignmentEngine, AlignmentError, AlignmentResult
from src.services.audio import WavFileError, read_pcm_wav


@dataclass(frozen=True)
class UploadedAlignmentResult:
    sample_rate: int
    alignment: AlignmentResult
    alignment_supported: bool
    alignment_error: Optional[str]
    alignment_mode: str


def align_uploaded_wav(
    *,
    request_data: UploadedAlignmentRequest,
    alignment_engine: AlignmentEngine,
) -> UploadedAlignmentResult:
    try:
        audio = read_pcm_wav(request_data.audio_bytes)
    except WavFileError as exc:
        raise RequestValidationError(str(exc)) from exc

    if audio.sample_width != 2:
        raise RequestValidationError("audio must be 16-bit PCM WAV")

    alignment_mode = alignment_engine.mode
    alignment_supported = True
    alignment_error: Optional[str] = None

    try:
        alignment = alignment_engine.align(
            text=request_data.text,
            grammar=request_data.grammar,
            pcm_bytes=audio.pcm_bytes,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )
    except AlignmentError as exc:
        alignment_supported = False
        alignment_error = str(exc)
        alignment = AlignmentResult(sample_rate=audio.sample_rate)

    if alignment_supported and not alignment.words:
        alignment_supported = False
        alignment_error = "Alignment engine returned no words"

    return UploadedAlignmentResult(
        sample_rate=audio.sample_rate,
        alignment=alignment,
        alignment_supported=alignment_supported,
        alignment_error=alignment_error,
        alignment_mode=alignment_mode,
    )
