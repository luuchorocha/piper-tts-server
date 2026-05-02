"""Piper-native word alignment using phoneme-level timing from the TTS model.

When Piper synthesizes with ``include_alignments=True`` and the ONNX model has
been patched (two outputs), each ``AudioChunk`` carries a list of
``PhonemeAlignment`` objects with exact per-phoneme sample counts.  The space
phoneme (``" "``) inserted by espeak-ng between words serves as a definitive
word boundary delimiter, giving sample-accurate word timestamps without any
external acoustic model.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from src.services.alignment.models import (
    AlignmentResult,
    PhonemeTimestamp,
    WordTimestamp,
)
from src.services.alignment.service import AlignmentError

LOGGER = logging.getLogger(__name__)

BOS = "^"
EOS = "$"
SPACE = " "


def align_from_piper_phonemes(
    *,
    text: str,
    chunk_alignments: Sequence[Sequence[Any]],
    chunk_sample_rates: Sequence[int],
    chunk_time_offsets: Sequence[float],
) -> AlignmentResult:
    """Build word-level timestamps from Piper's native phoneme alignment data.

    Args:
        text: The original input text that was synthesized.
        chunk_alignments: Per-sentence list of ``PhonemeAlignment`` objects
            (each has ``.phoneme``, ``.num_samples``).
        chunk_sample_rates: Sample rate for each chunk (Hz).
        chunk_time_offsets: Absolute start time (seconds) of each chunk within
            the final WAV (accounts for inter-sentence silence).

    Returns:
        An ``AlignmentResult`` with word-level and phoneme-level timestamps.

    Raises:
        AlignmentError: When the derived word count does not match the input
            text, or when no usable alignment data is provided.
    """
    if not chunk_alignments or all(not ca for ca in chunk_alignments):
        raise AlignmentError("No Piper phoneme alignment data available")

    text_words = text.split()
    if not text_words:
        raise AlignmentError("Empty text for Piper native alignment")

    all_phonemes: list[PhonemeTimestamp] = []
    all_words: list[WordTimestamp] = []

    # Accumulate phonemes for the current word being built
    word_phonemes: list[PhonemeTimestamp] = []
    word_phoneme_start_indices: list[int] = []

    for chunk_idx, alignments in enumerate(chunk_alignments):
        sample_rate = chunk_sample_rates[chunk_idx]
        current_time = chunk_time_offsets[chunk_idx]

        for alignment in alignments:
            phoneme = alignment.phoneme
            duration = alignment.num_samples / sample_rate
            end_time = current_time + duration

            if phoneme in (BOS, EOS):
                current_time = end_time
                continue

            if phoneme == SPACE:
                # Word boundary — finalize current word group
                if word_phonemes:
                    _finalize_word(
                        text_words=text_words,
                        word_index=len(all_words),
                        word_phonemes=word_phonemes,
                        word_phoneme_start_indices=word_phoneme_start_indices,
                        all_words=all_words,
                    )
                    word_phonemes = []
                    word_phoneme_start_indices = []

                current_time = end_time
                continue

            # Regular phoneme — add to current word group
            pt = PhonemeTimestamp(
                phoneme=phoneme,
                start=current_time,
                end=end_time,
            )
            word_phoneme_start_indices.append(len(all_phonemes))
            all_phonemes.append(pt)
            word_phonemes.append(pt)

            current_time = end_time

        # End of chunk — finalize any remaining word group (last word in sentence)
        if word_phonemes:
            _finalize_word(
                text_words=text_words,
                word_index=len(all_words),
                word_phonemes=word_phonemes,
                word_phoneme_start_indices=word_phoneme_start_indices,
                all_words=all_words,
            )
            word_phonemes = []
            word_phoneme_start_indices = []

    if len(all_words) != len(text_words):
        raise AlignmentError(
            f"Piper native alignment produced {len(all_words)} word(s) "
            f"but text has {len(text_words)}: {text!r}"
        )

    sample_rate = chunk_sample_rates[0] if chunk_sample_rates else 22050
    return AlignmentResult(
        phonemes=all_phonemes,
        words=all_words,
        sample_rate=sample_rate,
    )


def _finalize_word(
    *,
    text_words: list[str],
    word_index: int,
    word_phonemes: list[PhonemeTimestamp],
    word_phoneme_start_indices: list[int],
    all_words: list[WordTimestamp],
) -> None:
    """Create a ``WordTimestamp`` from accumulated phonemes and append it."""
    original_word = text_words[word_index] if word_index < len(text_words) else "?"
    all_words.append(
        WordTimestamp(
            word=original_word,
            start=word_phonemes[0].start,
            end=word_phonemes[-1].end,
            phoneme_indices=tuple(word_phoneme_start_indices),
        )
    )


__all__ = ["align_from_piper_phonemes"]
