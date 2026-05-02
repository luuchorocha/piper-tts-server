"""Data models for phoneme and word-level alignment timestamps."""

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class PhonemeTimestamp:
    """A phoneme with its timing in seconds."""

    phoneme: str
    start: float
    end: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "phoneme": self.phoneme,
            "start": round(self.start, 4),
            "end": round(self.end, 4),
        }


@dataclass(frozen=True)
class WordTimestamp:
    """A word with its timing in seconds and indices into the phoneme list."""

    word: str
    start: float
    end: float
    phoneme_indices: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "start": round(self.start, 4),
            "end": round(self.end, 4),
        }


@dataclass
class AlignmentResult:
    """Container for all alignment data from a synthesis operation."""

    phonemes: list[PhonemeTimestamp] = field(default_factory=list)
    words: list[WordTimestamp] = field(default_factory=list)
    sample_rate: int = 22050

    def to_dict(self) -> dict[str, Any]:
        return {
            "words": [w.to_dict() for w in self.words],
        }


def phoneme_alignments_to_timestamps(
    piper_alignments: Sequence[Any],
    sample_rate: int,
    time_offset: float = 0.0,
) -> list[PhonemeTimestamp]:
    """Convert Piper PhonemeAlignment objects to PhonemeTimestamp list.

    Args:
        piper_alignments: List of piper.PhonemeAlignment objects
        sample_rate: Audio sample rate in Hz
        time_offset: Starting time offset in seconds (for multi-chunk stitching)

    Returns:
        List of PhonemeTimestamp with absolute times in seconds
    """
    result: list[PhonemeTimestamp] = []
    current_time = time_offset

    for alignment in piper_alignments:
        duration = alignment.num_samples / sample_rate
        end_time = current_time + duration

        # Skip BOS/EOS markers (empty or special phonemes)
        phoneme = alignment.phoneme
        if phoneme and phoneme not in ("^", "$"):
            result.append(
                PhonemeTimestamp(
                    phoneme=phoneme,
                    start=current_time,
                    end=end_time,
                )
            )

        current_time = end_time

    return result
