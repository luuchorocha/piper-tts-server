"""Silence-based word alignment using provided grammar hints.

This aligner intentionally avoids model-provided phoneme timestamps.
It uses energy-based silence detection on rendered PCM audio, then
projects grammar phrases/words into detected speech regions.
"""

from __future__ import annotations

import re
from array import array
from dataclasses import dataclass
from typing import Sequence

from src.services.alignment.models import AlignmentResult, PhonemeTimestamp, WordTimestamp

_WORD_RE = re.compile(r"\S+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+")


@dataclass(frozen=True)
class _Region:
    start: float
    end: float


def _tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _default_grammar_phrases(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    return parts or [text]


def _parse_grammar_phrases(grammar: Sequence[str] | None, fallback_text: str) -> list[str]:
    if not grammar:
        return _default_grammar_phrases(fallback_text)

    phrases = [p.strip() for p in grammar if isinstance(p, str) and p.strip()]
    return phrases or _default_grammar_phrases(fallback_text)


def _pcm_to_mono_samples(pcm_bytes: bytes, channels: int) -> array:
    samples = array("h")
    samples.frombytes(pcm_bytes)

    if channels <= 1:
        return samples

    return array("h", samples[::channels])


def _detect_speech_regions(
    *,
    pcm_bytes: bytes,
    sample_rate: int,
    channels: int,
    silence_threshold: int = 450,
    window_ms: int = 20,
    min_speech_ms: int = 60,
    min_silence_ms: int = 90,
) -> list[_Region]:
    mono = _pcm_to_mono_samples(pcm_bytes, channels)
    if not mono:
        return []

    window_size = max(1, int(sample_rate * window_ms / 1000.0))
    min_speech_windows = max(1, int(min_speech_ms / window_ms))
    min_silence_windows = max(1, int(min_silence_ms / window_ms))

    energies: list[float] = []
    mono_len = len(mono)
    for i in range(0, mono_len, window_size):
        end = min(i + window_size, mono_len)
        if i >= end:
            break
        total = 0
        for j in range(i, end):
            v = mono[j]
            total += v if v >= 0 else -v
        energies.append(total / (end - i))

    regions: list[_Region] = []
    in_speech = False
    speech_start = 0
    quiet_run = 0

    for idx, energy in enumerate(energies):
        is_speech = energy >= silence_threshold
        if is_speech:
            quiet_run = 0
            if not in_speech:
                in_speech = True
                speech_start = idx
            continue

        if in_speech:
            quiet_run += 1
            if quiet_run >= min_silence_windows:
                speech_end = idx - quiet_run + 1
                if speech_end - speech_start >= min_speech_windows:
                    regions.append(
                        _Region(
                            start=(speech_start * window_size) / sample_rate,
                            end=(speech_end * window_size) / sample_rate,
                        )
                    )
                in_speech = False
                quiet_run = 0

    if in_speech:
        speech_end = len(energies)
        if speech_end - speech_start >= min_speech_windows:
            regions.append(
                _Region(
                    start=(speech_start * window_size) / sample_rate,
                    end=min(1.0 * len(mono) / sample_rate, (speech_end * window_size) / sample_rate),
                )
            )

    return regions


def _chunk_count(total_items: int, total_chunks: int, chunk_index: int) -> int:
    base = total_items // total_chunks
    remainder = total_items % total_chunks
    return base + (1 if chunk_index < remainder else 0)


def _assign_word_counts_to_regions(word_count: int, regions: list[_Region]) -> list[int]:
    if word_count <= 0 or not regions:
        return []

    durations = [max(0.0, r.end - r.start) for r in regions]
    total_duration = sum(durations)

    if total_duration <= 0:
        counts = [0] * len(regions)
        counts[0] = word_count
        return counts

    raw_counts = [(d / total_duration) * word_count for d in durations]
    counts = [int(c) for c in raw_counts]
    assigned = sum(counts)

    # Assign remaining words to regions with largest fractional parts.
    remaining = word_count - assigned
    fractions = sorted(
        ((raw_counts[i] - counts[i], i) for i in range(len(regions))),
        reverse=True,
    )
    for _, region_index in fractions:
        if remaining <= 0:
            break
        counts[region_index] += 1
        remaining -= 1

    return counts


def _words_for_phrases(phrases: Sequence[str]) -> list[str]:
    words: list[str] = []
    for phrase in phrases:
        words.extend(_tokenize_words(phrase))
    return words


def align_from_silence_and_grammar(
    *,
    text: str,
    grammar: Sequence[str] | None,
    pcm_bytes: bytes,
    sample_rate: int,
    channels: int,
) -> AlignmentResult:
    phrases = _parse_grammar_phrases(grammar, text)
    aligned_words = _words_for_phrases(phrases)
    if not aligned_words:
        return AlignmentResult(sample_rate=sample_rate)

    regions = _detect_speech_regions(
        pcm_bytes=pcm_bytes,
        sample_rate=sample_rate,
        channels=channels,
    )

    total_duration = len(pcm_bytes) / max(1, sample_rate * channels * 2)
    if not regions and total_duration > 0:
        regions = [_Region(start=0.0, end=total_duration)]

    words: list[WordTimestamp] = []
    phonemes: list[PhonemeTimestamp] = []
    region_word_counts = _assign_word_counts_to_regions(len(aligned_words), regions)

    word_index = 0
    phoneme_index = 0

    for region, words_in_region in zip(regions, region_word_counts):
        if words_in_region <= 0:
            continue

        region_words = aligned_words[word_index : word_index + words_in_region]
        word_index += words_in_region
        if not region_words:
            continue

        duration = max(0.0, region.end - region.start)
        if duration <= 0:
            continue

        total_chars = sum(max(1, len(w)) for w in region_words)
        cursor = region.start
        for idx, word in enumerate(region_words):
            ratio = max(1, len(word)) / total_chars
            if idx == len(region_words) - 1:
                word_end = region.end
            else:
                word_end = min(region.end, cursor + duration * ratio)
            word_end = max(cursor, word_end)

            words.append(
                WordTimestamp(
                    word=word,
                    start=cursor,
                    end=word_end,
                    phoneme_indices=(phoneme_index,),
                )
            )
            phonemes.append(
                PhonemeTimestamp(
                    phoneme=word,
                    start=cursor,
                    end=word_end,
                )
            )
            phoneme_index += 1
            cursor = word_end

    return AlignmentResult(
        phonemes=phonemes,
        words=words,
        sample_rate=sample_rate,
    )
