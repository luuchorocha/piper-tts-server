from dataclasses import dataclass

from starlette.datastructures import FormData, UploadFile

from src.core.constants import MAX_AUDIO_UPLOAD_BYTES, MAX_TEXT_LENGTH
from src.parsers.synthesis.request import RequestValidationError, parse_optional_grammar


class AudioUploadTooLarge(RequestValidationError):
    pass


@dataclass(frozen=True)
class UploadedAlignmentRequest:
    audio_bytes: bytes
    text: str
    grammar: tuple[str, ...] | None
    filename: str | None
    content_type: str | None


async def _read_upload_bytes(
    upload: UploadFile,
    *,
    max_audio_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break

        total += len(chunk)
        if total > max_audio_bytes:
            raise AudioUploadTooLarge(
                f"audio exceeds maximum upload size of {max_audio_bytes // (1024 * 1024)} MB",
            )
        chunks.append(chunk)

    return b"".join(chunks)


def _parse_text(value: object) -> str:
    if not isinstance(value, str):
        raise RequestValidationError("text must be a string")

    text = value.strip()
    if not text:
        raise RequestValidationError("No text provided")
    if len(text) > MAX_TEXT_LENGTH:
        raise RequestValidationError(
            f"Text exceeds maximum length of {MAX_TEXT_LENGTH} characters",
        )

    return text


def _parse_grammar(form: FormData) -> tuple[str, ...] | None:
    grammar_values = form.getlist("grammar")
    if not grammar_values:
        return None

    if len(grammar_values) == 1:
        return parse_optional_grammar(grammar_values[0])

    return parse_optional_grammar(grammar_values)


async def parse_uploaded_alignment_request(
    form: FormData,
    *,
    max_audio_bytes: int = MAX_AUDIO_UPLOAD_BYTES,
) -> UploadedAlignmentRequest:
    audio = form.get("audio")
    if audio is None:
        raise RequestValidationError("audio file is required")
    if not isinstance(audio, UploadFile):
        raise RequestValidationError("audio must be a file upload")

    text = _parse_text(form.get("text"))
    grammar = _parse_grammar(form)
    try:
        audio_bytes = await _read_upload_bytes(audio, max_audio_bytes=max_audio_bytes)
    finally:
        await audio.close()

    if not audio_bytes:
        raise RequestValidationError("audio file is empty")

    return UploadedAlignmentRequest(
        audio_bytes=audio_bytes,
        text=text,
        grammar=grammar,
        filename=audio.filename,
        content_type=audio.content_type,
    )
