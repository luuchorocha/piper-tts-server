"""Word boundary detection and phoneme-to-word grouping."""

import re
from typing import Sequence

from piper_http.services.alignment.models import (
    PhonemeTimestamp,
    WordTimestamp,
)

# Pattern to split text into word tokens (preserving whitespace boundaries)
_WORD_SPLIT_RE = re.compile(r"(\s+)")


def group_phonemes_into_words(
    text: str,
    phonemes: Sequence[PhonemeTimestamp],
) -> list[WordTimestamp]:
    """Group phonemes into words based on the original text.

    Strategy:
    - Split original text by whitespace to get word tokens
    - Distribute phonemes sequentially across words
    - Each word gets phonemes proportionally (best-effort heuristic)

    This is a heuristic approach since Piper's phonemes don't have explicit
    word boundary markers. For most TTS use cases, distributing phonemes
    evenly across detected words provides reasonable word-level timing.

    Args:
        text: Original input text
        phonemes: List of phoneme timestamps from synthesis

    Returns:
        List of WordTimestamp objects
    """
    if not phonemes:
        return []

    # Extract words from text (non-whitespace runs)
    words = [w for w in _WORD_SPLIT_RE.split(text.strip()) if w and not w.isspace()]

    if not words:
        return []

    # If only one word, all phonemes belong to it
    if len(words) == 1:
        return [
            WordTimestamp(
                word=words[0],
                start=phonemes[0].start,
                end=phonemes[-1].end,
                phoneme_indices=tuple(range(len(phonemes))),
            )
        ]

    # Distribute phonemes across words proportionally by character count
    total_chars = sum(len(w) for w in words)
    if total_chars == 0:
        return []

    result: list[WordTimestamp] = []
    phoneme_idx = 0
    total_phonemes = len(phonemes)

    for word_idx, word in enumerate(words):
        if phoneme_idx >= total_phonemes:
            break

        # Calculate how many phonemes this word should get
        word_ratio = len(word) / total_chars
        expected_phonemes = max(1, round(word_ratio * total_phonemes))

        # For the last word, take all remaining phonemes
        if word_idx == len(words) - 1:
            phonemes_for_word = total_phonemes - phoneme_idx
        else:
            phonemes_for_word = min(expected_phonemes, total_phonemes - phoneme_idx)

        if phonemes_for_word <= 0:
            continue

        word_phoneme_indices = tuple(
            range(phoneme_idx, phoneme_idx + phonemes_for_word)
        )
        word_start = phonemes[phoneme_idx].start
        word_end = phonemes[phoneme_idx + phonemes_for_word - 1].end

        result.append(
            WordTimestamp(
                word=word,
                start=word_start,
                end=word_end,
                phoneme_indices=word_phoneme_indices,
            )
        )

        phoneme_idx += phonemes_for_word

    return result
