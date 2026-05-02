import argparse
import asyncio
import io
import json
import unittest
import wave

from starlette.datastructures import FormData, Headers, UploadFile
from starlette.requests import Request

from src.api.routes.alignments import build_alignments_handler
from src.core.context import AppContext, SynthesisCapacity
from src.parsers.alignments import (
    AudioUploadTooLarge,
    parse_uploaded_alignment_request,
)
from src.parsers.synthesis.request import RequestValidationError
from src.services.alignment.models import AlignmentResult, WordTimestamp
from src.services.alignment.service import AlignmentError
from src.services.alignments import align_uploaded_wav


def _wav_bytes(
    *,
    sample_rate: int = 16_000,
    channels: int = 1,
    sample_width: int = 2,
    frames: bytes | None = None,
) -> bytes:
    if frames is None:
        frames = b"\x00" * sample_width * channels * 32

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setframerate(sample_rate)
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.writeframes(frames)

    return buffer.getvalue()


def _upload(content: bytes) -> UploadFile:
    return UploadFile(
        io.BytesIO(content),
        filename="speech.wav",
        headers=Headers({"content-type": "audio/wav"}),
    )


def _multipart_request(*, audio: bytes | None = None, text: str | None = "hello") -> Request:
    boundary = "----test-boundary"
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    def add_file(name: str, filename: str, content: bytes) -> None:
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: audio/wav\r\n\r\n"
            ).encode("ascii")
        )
        body.extend(content)
        body.extend(b"\r\n")

    if audio is not None:
        add_file("audio", "speech.wav", audio)
    if text is not None:
        add_field("text", text)
    add_field("grammar", "hello|world")
    body.extend(f"--{boundary}--\r\n".encode("ascii"))

    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}

        sent = True
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/alignments",
        "raw_path": b"/alignments",
        "query_string": b"",
        "headers": [
            (b"content-type", f"multipart/form-data; boundary={boundary}".encode("ascii")),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


class _RecordingAlignmentEngine:
    mode = "forced_ctc"

    def __init__(self) -> None:
        self.calls = []

    def align(self, **kwargs):
        self.calls.append(kwargs)
        return AlignmentResult(
            words=[
                WordTimestamp(word="hello", start=0.0, end=0.1, phoneme_indices=()),
            ],
            sample_rate=kwargs["sample_rate"],
        )


class _FailingAlignmentEngine:
    mode = "forced_ctc"

    def align(self, **kwargs):
        del kwargs
        raise AlignmentError("forced alignment failed")


class UploadedAlignmentParserTest(unittest.TestCase):
    def test_parser_accepts_upload_text_and_repeated_grammar(self):
        form = FormData([
            ("audio", _upload(_wav_bytes())),
            ("text", " hello "),
            ("grammar", "hello"),
            ("grammar", "world"),
        ])

        result = asyncio.run(parse_uploaded_alignment_request(form))

        self.assertEqual("hello", result.text)
        self.assertEqual(("hello", "world"), result.grammar)
        self.assertTrue(result.audio_bytes.startswith(b"RIFF"))

    def test_parser_rejects_missing_text(self):
        form = FormData([("audio", _upload(_wav_bytes()))])

        with self.assertRaisesRegex(RequestValidationError, "text must be a string"):
            asyncio.run(parse_uploaded_alignment_request(form))

    def test_parser_enforces_upload_limit(self):
        form = FormData([
            ("audio", _upload(b"abc")),
            ("text", "hello"),
        ])

        with self.assertRaises(AudioUploadTooLarge):
            asyncio.run(parse_uploaded_alignment_request(form, max_audio_bytes=2))


class UploadedAlignmentServiceTest(unittest.TestCase):
    def test_service_aligns_wav_with_existing_engine(self):
        form = FormData([
            ("audio", _upload(_wav_bytes(sample_rate=8_000, channels=2))),
            ("text", "hello"),
            ("grammar", "hello|world"),
        ])
        request_data = asyncio.run(parse_uploaded_alignment_request(form))
        engine = _RecordingAlignmentEngine()

        result = align_uploaded_wav(request_data=request_data, alignment_engine=engine)

        self.assertTrue(result.alignment_supported)
        self.assertEqual(8_000, result.sample_rate)
        self.assertEqual("forced_ctc", result.alignment_mode)
        self.assertEqual(2, engine.calls[0]["channels"])
        self.assertEqual(("hello", "world"), engine.calls[0]["grammar"])

    def test_service_rejects_invalid_wav(self):
        form = FormData([
            ("audio", _upload(b"not a wav")),
            ("text", "hello"),
        ])
        request_data = asyncio.run(parse_uploaded_alignment_request(form))

        with self.assertRaisesRegex(RequestValidationError, "readable WAV"):
            align_uploaded_wav(
                request_data=request_data,
                alignment_engine=_RecordingAlignmentEngine(),
            )

    def test_service_rejects_non_16_bit_wav(self):
        form = FormData([
            ("audio", _upload(_wav_bytes(sample_width=1))),
            ("text", "hello"),
        ])
        request_data = asyncio.run(parse_uploaded_alignment_request(form))

        with self.assertRaisesRegex(RequestValidationError, "16-bit PCM"):
            align_uploaded_wav(
                request_data=request_data,
                alignment_engine=_RecordingAlignmentEngine(),
            )

    def test_service_returns_unsupported_payload_for_alignment_failure(self):
        form = FormData([
            ("audio", _upload(_wav_bytes())),
            ("text", "hello"),
        ])
        request_data = asyncio.run(parse_uploaded_alignment_request(form))

        result = align_uploaded_wav(
            request_data=request_data,
            alignment_engine=_FailingAlignmentEngine(),
        )

        self.assertFalse(result.alignment_supported)
        self.assertEqual("forced alignment failed", result.alignment_error)
        self.assertEqual([], result.alignment.words)


class UploadedAlignmentRouteTest(unittest.TestCase):
    def _handler(self, alignment_engine):
        args = argparse.Namespace(synthesis_acquire_timeout_seconds=5)
        context = AppContext(
            args=args,
            data_dirs=[],
            voice_manager=object(),
            synthesis_capacity=SynthesisCapacity(
                limit=1,
                acquire_timeout_seconds=5,
                max_waiters=1,
            ),
            alignment_engine=alignment_engine,
        )
        return build_alignments_handler(context)

    def test_route_returns_word_timestamps_without_audio(self):
        engine = _RecordingAlignmentEngine()
        response = asyncio.run(
            self._handler(engine)(_multipart_request(audio=_wav_bytes(), text="hello"))
        )

        self.assertEqual(200, response.status_code)
        payload = json.loads(response.body)
        self.assertEqual("forced_ctc", payload["alignment_mode"])
        self.assertTrue(payload["alignment_supported"])
        self.assertEqual("hello", payload["alignments"]["words"][0]["word"])
        self.assertNotIn("audio_base64", payload)
        self.assertEqual("hello", engine.calls[0]["text"])

    def test_route_rejects_non_multipart_requests(self):
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": b"{}", "more_body": False}

        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "path": "/alignments",
                "raw_path": b"/alignments",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
                "scheme": "http",
            },
            receive,
        )

        response = asyncio.run(self._handler(_RecordingAlignmentEngine())(request))

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Content-Type must be multipart/form-data",
            json.loads(response.body)["error"],
        )

    def test_route_surfaces_alignment_failure_payload(self):
        response = asyncio.run(
            self._handler(_FailingAlignmentEngine())(
                _multipart_request(audio=_wav_bytes(), text="hello")
            )
        )

        self.assertEqual(200, response.status_code)
        payload = json.loads(response.body)
        self.assertFalse(payload["alignment_supported"])
        self.assertEqual("forced alignment failed", payload["alignment_error"])


if __name__ == "__main__":
    unittest.main()
