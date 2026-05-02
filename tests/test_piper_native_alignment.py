import unittest
from dataclasses import dataclass

from src.services.alignment.piper_native import align_from_piper_phonemes
from src.services.alignment.service import AlignmentError


@dataclass
class _FakePhonemeAlignment:
    """Mimics piper.PhonemeAlignment for testing."""

    phoneme: str
    num_samples: int
    phoneme_ids: tuple = ()


class PiperNativeAlignmentTest(unittest.TestCase):
    """Tests for the Piper-native word alignment module."""

    def test_single_word(self):
        # "Hello" → BOS, h, ə, l, ˈ, o, ʊ, EOS
        alignments = [
            _FakePhonemeAlignment("^", 768),
            _FakePhonemeAlignment("h", 768),
            _FakePhonemeAlignment("ə", 1536),
            _FakePhonemeAlignment("l", 512),
            _FakePhonemeAlignment("ˈ", 768),
            _FakePhonemeAlignment("o", 768),
            _FakePhonemeAlignment("ʊ", 1024),
            _FakePhonemeAlignment("$", 1536),
        ]
        result = align_from_piper_phonemes(
            text="Hello",
            chunk_alignments=[alignments],
            chunk_sample_rates=[16000],
            chunk_time_offsets=[0.0],
        )

        self.assertEqual(1, len(result.words))
        self.assertEqual("Hello", result.words[0].word)
        # BOS = 768 samples @ 16kHz = 0.048s → word starts at 0.048
        self.assertAlmostEqual(0.048, result.words[0].start, places=4)
        # Last phoneme ends at BOS + h + ə + l + ˈ + o + ʊ
        # = 768 + 768 + 1536 + 512 + 768 + 768 + 1024 = 6144 samples
        # 6144 / 16000 = 0.384s
        self.assertAlmostEqual(0.384, result.words[0].end, places=4)

    def test_two_words_split_by_space(self):
        # "Hello world" → BOS, h, ə, l, ˈ, o, ʊ, SPACE, w, ˈ, ɜ, ː, l, d, EOS
        alignments = [
            _FakePhonemeAlignment("^", 768),
            _FakePhonemeAlignment("h", 768),
            _FakePhonemeAlignment("ə", 1536),
            _FakePhonemeAlignment("l", 512),
            _FakePhonemeAlignment("ˈ", 768),
            _FakePhonemeAlignment("o", 768),
            _FakePhonemeAlignment("ʊ", 1024),
            _FakePhonemeAlignment(" ", 1024),
            _FakePhonemeAlignment("w", 768),
            _FakePhonemeAlignment("ˈ", 1280),
            _FakePhonemeAlignment("ɜ", 768),
            _FakePhonemeAlignment("ː", 1024),
            _FakePhonemeAlignment("l", 1280),
            _FakePhonemeAlignment("d", 1536),
            _FakePhonemeAlignment("$", 1536),
        ]
        result = align_from_piper_phonemes(
            text="Hello world",
            chunk_alignments=[alignments],
            chunk_sample_rates=[16000],
            chunk_time_offsets=[0.0],
        )

        self.assertEqual(2, len(result.words))
        self.assertEqual("Hello", result.words[0].word)
        self.assertEqual("world", result.words[1].word)

        # "Hello" phonemes start after BOS (768 samples = 0.048s)
        self.assertAlmostEqual(0.048, result.words[0].start, places=4)
        # "Hello" ends at BOS + h + ə + l + ˈ + o + ʊ = 6144 / 16000 = 0.384s
        self.assertAlmostEqual(0.384, result.words[0].end, places=4)

        # "world" starts after space: 6144 + 1024 (space) = 7168 / 16000 = 0.448s
        self.assertAlmostEqual(0.448, result.words[1].start, places=4)

    def test_punctuation_stays_with_word(self):
        # "hat, is" → BOS, h, æ, t, COMMA, SPACE, ɪ, z, EOS
        # The comma and space phonemes: comma attaches to "hat,", space is delimiter
        alignments = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("h", 512),
            _FakePhonemeAlignment("ˈ", 256),
            _FakePhonemeAlignment("æ", 512),
            _FakePhonemeAlignment("t", 512),
            _FakePhonemeAlignment(",", 256),
            _FakePhonemeAlignment(" ", 512),
            _FakePhonemeAlignment("ɪ", 512),
            _FakePhonemeAlignment("z", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        result = align_from_piper_phonemes(
            text="hat, is",
            chunk_alignments=[alignments],
            chunk_sample_rates=[16000],
            chunk_time_offsets=[0.0],
        )

        self.assertEqual(2, len(result.words))
        self.assertEqual("hat,", result.words[0].word)
        self.assertEqual("is", result.words[1].word)

    def test_contraction_is_single_word(self):
        # "don't" has no internal space → single word group
        alignments = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("d", 512),
            _FakePhonemeAlignment("ˈ", 256),
            _FakePhonemeAlignment("o", 512),
            _FakePhonemeAlignment("ʊ", 512),
            _FakePhonemeAlignment("n", 512),
            _FakePhonemeAlignment("t", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        result = align_from_piper_phonemes(
            text="don't",
            chunk_alignments=[alignments],
            chunk_sample_rates=[16000],
            chunk_time_offsets=[0.0],
        )

        self.assertEqual(1, len(result.words))
        self.assertEqual("don't", result.words[0].word)

    def test_multi_chunk_with_time_offsets(self):
        # "Hello! How are you?" → 2 chunks (espeak splits on "!")
        chunk1 = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("h", 512),
            _FakePhonemeAlignment("ə", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        chunk2 = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("h", 512),
            _FakePhonemeAlignment("aʊ", 512),
            _FakePhonemeAlignment(" ", 256),
            _FakePhonemeAlignment("ɑː", 512),
            _FakePhonemeAlignment("ɹ", 512),
            _FakePhonemeAlignment(" ", 256),
            _FakePhonemeAlignment("j", 512),
            _FakePhonemeAlignment("uː", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        # Chunk 2 starts 0.2s into the WAV (chunk1 duration + sentence silence)
        result = align_from_piper_phonemes(
            text="Hello! How are you?",
            chunk_alignments=[chunk1, chunk2],
            chunk_sample_rates=[16000, 16000],
            chunk_time_offsets=[0.0, 0.2],
        )

        self.assertEqual(4, len(result.words))
        self.assertEqual("Hello!", result.words[0].word)
        self.assertEqual("How", result.words[1].word)
        self.assertEqual("are", result.words[2].word)
        self.assertEqual("you?", result.words[3].word)

        # Chunk 1: "Hello!" starts at BOS end = 512/16000 = 0.032s
        self.assertAlmostEqual(0.032, result.words[0].start, places=4)

        # Chunk 2 words start relative to chunk_time_offset=0.2
        # "How" starts at 0.2 + BOS(512) = 0.2 + 0.032 = 0.232
        self.assertAlmostEqual(0.232, result.words[1].start, places=4)

    def test_word_count_mismatch_raises_alignment_error(self):
        # Text has 2 words but phonemes produce only 1 group (no space)
        alignments = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("h", 512),
            _FakePhonemeAlignment("ə", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        with self.assertRaises(AlignmentError) as ctx:
            align_from_piper_phonemes(
                text="Hello world",
                chunk_alignments=[alignments],
                chunk_sample_rates=[16000],
                chunk_time_offsets=[0.0],
            )
        self.assertIn("1 word(s)", str(ctx.exception))
        self.assertIn("2", str(ctx.exception))

    def test_empty_alignments_raises_alignment_error(self):
        with self.assertRaises(AlignmentError):
            align_from_piper_phonemes(
                text="Hello",
                chunk_alignments=[[]],
                chunk_sample_rates=[16000],
                chunk_time_offsets=[0.0],
            )

    def test_none_like_alignments_raises_alignment_error(self):
        with self.assertRaises(AlignmentError):
            align_from_piper_phonemes(
                text="Hello",
                chunk_alignments=[],
                chunk_sample_rates=[],
                chunk_time_offsets=[],
            )

    def test_bos_eos_do_not_produce_phoneme_entries(self):
        alignments = [
            _FakePhonemeAlignment("^", 1000),
            _FakePhonemeAlignment("h", 500),
            _FakePhonemeAlignment("$", 1000),
        ]
        result = align_from_piper_phonemes(
            text="h",
            chunk_alignments=[alignments],
            chunk_sample_rates=[16000],
            chunk_time_offsets=[0.0],
        )

        # Only 1 phoneme timestamp (the "h"), not BOS/EOS
        self.assertEqual(1, len(result.phonemes))
        self.assertEqual("h", result.phonemes[0].phoneme)
        # Word start = after BOS = 1000/16000 = 0.0625
        self.assertAlmostEqual(0.0625, result.words[0].start, places=4)
        # Word end = BOS + h = (1000 + 500) / 16000 = 0.09375
        self.assertAlmostEqual(0.09375, result.words[0].end, places=5)

    def test_phoneme_indices_are_correct(self):
        alignments = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("h", 512),
            _FakePhonemeAlignment("ə", 512),
            _FakePhonemeAlignment(" ", 256),
            _FakePhonemeAlignment("w", 512),
            _FakePhonemeAlignment("ɜ", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        result = align_from_piper_phonemes(
            text="Hi we",
            chunk_alignments=[alignments],
            chunk_sample_rates=[16000],
            chunk_time_offsets=[0.0],
        )

        # "Hi" gets phonemes at indices 0 (h) and 1 (ə)
        self.assertEqual((0, 1), result.words[0].phoneme_indices)
        # "we" gets phonemes at indices 2 (w) and 3 (ɜ)
        self.assertEqual((2, 3), result.words[1].phoneme_indices)

    def test_empty_text_raises_alignment_error(self):
        with self.assertRaises(AlignmentError):
            align_from_piper_phonemes(
                text="",
                chunk_alignments=[[]],
                chunk_sample_rates=[16000],
                chunk_time_offsets=[0.0],
            )

    def test_sample_rate_is_preserved(self):
        alignments = [
            _FakePhonemeAlignment("^", 512),
            _FakePhonemeAlignment("h", 512),
            _FakePhonemeAlignment("$", 512),
        ]
        result = align_from_piper_phonemes(
            text="h",
            chunk_alignments=[alignments],
            chunk_sample_rates=[22050],
            chunk_time_offsets=[0.0],
        )

        self.assertEqual(22050, result.sample_rate)


if __name__ == "__main__":
    unittest.main()
