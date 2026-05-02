import argparse
import unittest
from dataclasses import dataclass
from typing import Optional

from src.parsers.synthesis.request import SynthesisRequest
from src.services.alignment.models import AlignmentResult, WordTimestamp
from src.services.alignment.service import AlignmentError
from src.services.synthesis.service import synthesize_text


@dataclass
class _FakePhonemeAlignment:
    phoneme: str
    num_samples: int
    phoneme_ids: tuple = ()


@dataclass
class _FakeChunk:
    sample_rate: int = 22_050
    sample_width: int = 2
    sample_channels: int = 1
    audio_int16_bytes: bytes = b"\x00\x00" * 32
    phoneme_alignments: Optional[list] = None


class _FakeVoiceConfig:
    num_speakers = 1
    length_scale = 1.0
    noise_scale = 0.667
    noise_w_scale = 0.8
    speaker_id_map = {}


class _FakeVoice:
    def __init__(self, chunks=None):
        self.config = _FakeVoiceConfig()
        self._chunks = chunks

    def synthesize(self, text, config, include_alignments=False):
        del text, config
        if self._chunks is not None:
            yield from self._chunks
        else:
            yield _FakeChunk()


class _SuccessfulAlignmentEngine:
    mode = "forced_ctc"

    def align(self, **kwargs):
        del kwargs
        return AlignmentResult(
            words=[
                WordTimestamp(word="hello", start=0.0, end=0.1, phoneme_indices=()),
            ],
            sample_rate=22_050,
        )


class _FailingAlignmentEngine:
    mode = "forced_ctc"

    def align(self, **kwargs):
        del kwargs
        raise AlignmentError("forced alignment failed")


class SynthesizeTextTest(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(
            speaker=None,
            length_scale=None,
            noise_scale=None,
            noise_w_scale=None,
        )
        self.request = SynthesisRequest(
            text="hello",
            requested_voice="en_US-lessac-low",
            speaker_id=None,
            speaker=None,
            sentence_silence=0.0,
            length_scale=1.0,
            noise_scale=0.667,
            noise_w_scale=0.8,
            normalize_audio=True,
            volume=1.0,
            include_alignments=True,
            grammar=None,
            has_length_scale=False,
            has_noise_scale=False,
            has_noise_w_scale=False,
        )

    def test_synthesize_text_returns_alignment_mode_when_alignment_succeeds(self):
        result = synthesize_text(
            voice=_FakeVoice(),
            request_data=self.request,
            args=self.args,
            alignment_engine=_SuccessfulAlignmentEngine(),
            include_alignments=True,
        )

        self.assertTrue(result.alignment_supported)
        self.assertEqual("forced_ctc", result.alignment_mode)
        self.assertEqual("hello", result.alignment.words[0].word)

    def test_synthesize_text_sets_alignment_error_when_engine_fails(self):
        result = synthesize_text(
            voice=_FakeVoice(),
            request_data=self.request,
            args=self.args,
            alignment_engine=_FailingAlignmentEngine(),
            include_alignments=True,
        )

        self.assertFalse(result.alignment_supported)
        self.assertEqual("forced_ctc", result.alignment_mode)
        self.assertEqual("forced alignment failed", result.alignment_error)
        self.assertEqual([], result.alignment.words)

    def test_synthesize_text_uses_piper_native_alignment_when_available(self):
        chunk = _FakeChunk(
            sample_rate=16000,
            phoneme_alignments=[
                _FakePhonemeAlignment("^", 512),
                _FakePhonemeAlignment("h", 512),
                _FakePhonemeAlignment("ə", 512),
                _FakePhonemeAlignment("l", 512),
                _FakePhonemeAlignment("ˈ", 256),
                _FakePhonemeAlignment("o", 512),
                _FakePhonemeAlignment("ʊ", 512),
                _FakePhonemeAlignment("$", 512),
            ],
        )
        result = synthesize_text(
            voice=_FakeVoice(chunks=[chunk]),
            request_data=self.request,
            args=self.args,
            alignment_engine=_FailingAlignmentEngine(),
            include_alignments=True,
        )

        self.assertTrue(result.alignment_supported)
        self.assertEqual("piper_native", result.alignment_mode)
        self.assertEqual(1, len(result.alignment.words))
        self.assertEqual("hello", result.alignment.words[0].word)

    def test_synthesize_text_falls_back_to_ctc_when_no_phoneme_alignments(self):
        chunk = _FakeChunk(phoneme_alignments=None)
        result = synthesize_text(
            voice=_FakeVoice(chunks=[chunk]),
            request_data=self.request,
            args=self.args,
            alignment_engine=_SuccessfulAlignmentEngine(),
            include_alignments=True,
        )

        self.assertTrue(result.alignment_supported)
        self.assertEqual("forced_ctc", result.alignment_mode)
        self.assertEqual("hello", result.alignment.words[0].word)

    def test_synthesize_text_falls_back_to_ctc_when_native_alignment_fails(self):
        # Phonemes include a space producing 2 word groups, but text is 1 word
        chunk = _FakeChunk(
            sample_rate=16000,
            phoneme_alignments=[
                _FakePhonemeAlignment("^", 512),
                _FakePhonemeAlignment("h", 512),
                _FakePhonemeAlignment(" ", 256),
                _FakePhonemeAlignment("ə", 512),
                _FakePhonemeAlignment("$", 512),
            ],
        )
        result = synthesize_text(
            voice=_FakeVoice(chunks=[chunk]),
            request_data=self.request,
            args=self.args,
            alignment_engine=_SuccessfulAlignmentEngine(),
            include_alignments=True,
        )

        self.assertTrue(result.alignment_supported)
        self.assertEqual("forced_ctc", result.alignment_mode)

    def test_on_synthesis_complete_called_on_ctc_fallback(self):
        called = []
        synthesize_text(
            voice=_FakeVoice(),
            request_data=self.request,
            args=self.args,
            alignment_engine=_SuccessfulAlignmentEngine(),
            include_alignments=True,
            on_synthesis_complete=lambda: called.append(True),
        )
        self.assertEqual(1, len(called))

    def test_on_synthesis_complete_called_on_native_alignment(self):
        called = []
        chunk = _FakeChunk(
            sample_rate=16000,
            phoneme_alignments=[
                _FakePhonemeAlignment("^", 512),
                _FakePhonemeAlignment("h", 512),
                _FakePhonemeAlignment("ə", 512),
                _FakePhonemeAlignment("l", 512),
                _FakePhonemeAlignment("ˈ", 256),
                _FakePhonemeAlignment("o", 512),
                _FakePhonemeAlignment("ʊ", 512),
                _FakePhonemeAlignment("$", 512),
            ],
        )
        synthesize_text(
            voice=_FakeVoice(chunks=[chunk]),
            request_data=self.request,
            args=self.args,
            alignment_engine=_FailingAlignmentEngine(),
            include_alignments=True,
            on_synthesis_complete=lambda: called.append(True),
        )
        self.assertEqual(1, len(called))


if __name__ == "__main__":
    unittest.main()
