import unittest

from src.services.alignment.forced_ctc import ForcedCtcAlignmentEngine, _Point, _Segment
from src.services.alignment.service import AlignmentError


class ForcedCtcAlignmentEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = ForcedCtcAlignmentEngine()

    def test_build_transcript_words_normalizes_supported_english_tokens(self):
        words = self.engine._build_transcript_words("Hello, friend's... !!!  ")

        self.assertEqual(
            [("Hello,", "HELLO"), ("friend's...", "FRIEND'S")],
            words,
        )

    def test_build_transcript_words_rejects_non_english_alphanumeric_token(self):
        with self.assertRaisesRegex(AlignmentError, "unsupported token"):
            self.engine._build_transcript_words("hola año 123")

    def test_merge_words_collapses_segments_between_boundaries(self):
        segments = [
            _Segment(label="|", start=0, end=1, score=1.0),
            _Segment(label="H", start=1, end=3, score=0.9),
            _Segment(label="I", start=3, end=4, score=0.8),
            _Segment(label="|", start=4, end=5, score=1.0),
            _Segment(label="T", start=5, end=7, score=0.7),
            _Segment(label="H", start=7, end=8, score=0.6),
            _Segment(label="E", start=8, end=10, score=0.5),
            _Segment(label="|", start=10, end=11, score=1.0),
        ]

        words = self.engine._merge_words(segments)

        self.assertEqual(["HI", "THE"], [word.label for word in words])
        self.assertEqual((1, 4), (words[0].start, words[0].end))
        self.assertEqual((5, 10), (words[1].start, words[1].end))
        self.assertAlmostEqual((0.9 * 2 + 0.8 * 1) / 3, words[0].score)

    def test_merge_repeats_coalesces_adjacent_path_points(self):
        path = [
            _Point(token_index=0, time_index=0, score=0.9),
            _Point(token_index=0, time_index=1, score=0.8),
            _Point(token_index=1, time_index=2, score=0.7),
            _Point(token_index=1, time_index=3, score=0.6),
            _Point(token_index=2, time_index=4, score=0.5),
        ]

        segments = self.engine._merge_repeats(path, "|A|")

        self.assertEqual(["|", "A", "|"], [segment.label for segment in segments])
        self.assertEqual((0, 2), (segments[0].start, segments[0].end))
        self.assertEqual((2, 4), (segments[1].start, segments[1].end))
        self.assertAlmostEqual(0.85, segments[0].score)


if __name__ == "__main__":
    unittest.main()