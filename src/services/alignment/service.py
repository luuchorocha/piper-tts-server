from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Protocol, Sequence

from src.services.alignment.models import AlignmentResult
from src.services.alignment.silence_grammar import align_from_silence_and_grammar


class AlignmentError(RuntimeError):
    pass


class AlignmentUnavailableError(AlignmentError):
    pass


class AlignmentEngine(Protocol):
    mode: str

    def align(
        self,
        *,
        text: str,
        grammar: Sequence[str] | None,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int,
    ) -> AlignmentResult: ...


@dataclass
class SilenceGrammarAlignmentEngine:
    mode: str = "silence"

    def align(
        self,
        *,
        text: str,
        grammar: Sequence[str] | None,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int,
    ) -> AlignmentResult:
        return align_from_silence_and_grammar(
            text=text,
            grammar=grammar,
            pcm_bytes=pcm_bytes,
            sample_rate=sample_rate,
            channels=channels,
        )


def build_alignment_engine(args: argparse.Namespace) -> AlignmentEngine:
    method = getattr(args, "alignment_method", "forced_ctc")
    if method == "forced_ctc":
        from src.services.alignment.forced_ctc import ForcedCtcAlignmentEngine

        return ForcedCtcAlignmentEngine(
            bundle_name=getattr(args, "forced_aligner_bundle", "WAV2VEC2_ASR_BASE_960H"),
            min_word_score=float(getattr(args, "forced_aligner_min_word_score", 0.0)),
        )

    return SilenceGrammarAlignmentEngine()


__all__ = [
    "AlignmentEngine",
    "AlignmentError",
    "AlignmentUnavailableError",
    "SilenceGrammarAlignmentEngine",
    "build_alignment_engine",
]