import argparse
import asyncio
import json
import unittest
from unittest.mock import patch

from starlette.requests import Request

from src.api.routes.synthesis import build_synthesis_handler
from src.core.context import AppContext, SynthesisCapacity
from src.services.alignment.models import AlignmentResult, WordTimestamp
from src.services.synthesis.service import SynthesisResult


class _FakeVoiceManager:
    default_model_id = "en_US-lessac-low"

    def get(self, requested_voice):
        return {"voice": requested_voice}, False

    def offload(self, model_id):
        del model_id

    def release_ephemeral(self, voice):
        del voice


class _FakeAlignmentEngine:
    mode = "forced_ctc"


class SynthesisRouteTest(unittest.TestCase):
    def setUp(self):
        args = argparse.Namespace(
            sentence_silence=0.0,
            length_scale=None,
            noise_scale=None,
            noise_w_scale=None,
            synthesis_acquire_timeout_seconds=5,
        )
        context = AppContext(
            args=args,
            data_dirs=[],
            voice_manager=_FakeVoiceManager(),
            synthesis_capacity=SynthesisCapacity(
                limit=1,
                acquire_timeout_seconds=5,
                max_waiters=1,
            ),
            alignment_engine=_FakeAlignmentEngine(),
        )
        self.handler = build_synthesis_handler(context, force_alignments=True)

    def _build_request(self, payload):
        body = json.dumps(payload).encode("utf-8")
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}

            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/timestamps",
            "raw_path": b"/timestamps",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        return Request(scope, receive)

    def test_timestamps_route_returns_alignment_mode_and_forces_alignments(self):
        synthesis_result = SynthesisResult(
            wav_bytes=b"RIFFDATA",
            sample_rate=22_050,
            alignment=AlignmentResult(
                words=[WordTimestamp(word="hello", start=0.0, end=0.25, phoneme_indices=())],
                sample_rate=22_050,
            ),
            alignment_supported=True,
            alignment_error=None,
            alignment_mode="forced_ctc",
        )

        with patch("src.api.routes.synthesis.synthesize_text", return_value=synthesis_result) as synthesize_mock:
            response = asyncio.run(
                self.handler(
                    self._build_request({"text": "hello", "voice": "en_US-lessac-low"})
                )
            )

        self.assertEqual(200, response.status_code)
        payload = json.loads(response.body)
        self.assertEqual("forced_ctc", payload["alignment_mode"])
        self.assertTrue(payload["alignment_supported"])
        self.assertEqual("hello", payload["alignments"]["words"][0]["word"])
        self.assertIn("audio_base64", payload)

        self.assertTrue(synthesize_mock.called)
        self.assertTrue(synthesize_mock.call_args.kwargs["include_alignments"])
        self.assertEqual("forced_ctc", synthesize_mock.call_args.kwargs["alignment_engine"].mode)

    def test_timestamps_route_surfaces_alignment_failure_payload(self):
        synthesis_result = SynthesisResult(
            wav_bytes=b"RIFFDATA",
            sample_rate=22_050,
            alignment=AlignmentResult(words=[], sample_rate=22_050),
            alignment_supported=False,
            alignment_error="forced alignment failed",
            alignment_mode="forced_ctc",
        )

        with patch("src.api.routes.synthesis.synthesize_text", return_value=synthesis_result):
            response = asyncio.run(
                self.handler(
                    self._build_request({"text": "hello", "voice": "en_US-lessac-low"})
                )
            )

        self.assertEqual(200, response.status_code)
        payload = json.loads(response.body)
        self.assertFalse(payload["alignment_supported"])
        self.assertEqual("forced alignment failed", payload["alignment_error"])
        self.assertEqual("forced_ctc", payload["alignment_mode"])


if __name__ == "__main__":
    unittest.main()