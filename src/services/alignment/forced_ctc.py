"""English-first forced alignment using a torchaudio CTC acoustic model."""

from __future__ import annotations

import re
from array import array
from dataclasses import dataclass, field
from typing import Any, Sequence

from src.services.alignment.models import AlignmentResult, WordTimestamp
from src.services.alignment.service import AlignmentError, AlignmentUnavailableError

_NON_SPACE_RE = re.compile(r"\S+")
_NORMALIZE_RE = re.compile(r"[^A-Z']+")


@dataclass(frozen=True)
class _Point:
    token_index: int
    time_index: int
    score: float


@dataclass(frozen=True)
class _Segment:
    label: str
    start: int
    end: int
    score: float

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class ForcedCtcAlignmentEngine:
    bundle_name: str = "WAV2VEC2_ASR_BASE_960H"
    min_word_score: float = 0.0
    mode: str = "forced_ctc"
    _bundle: Any = field(default=None, init=False, repr=False)
    _model: Any = field(default=None, init=False, repr=False)
    _torch: Any = field(default=None, init=False, repr=False)
    _torchaudio: Any = field(default=None, init=False, repr=False)

    def align(
        self,
        *,
        text: str,
        grammar: Sequence[str] | None,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int,
    ) -> AlignmentResult:
        del grammar

        transcript_words = self._build_transcript_words(text)
        if not transcript_words:
            raise AlignmentError("Forced aligner could not derive any alignable words from the transcript")

        torch, torchaudio = self._load_runtime()
        bundle = self._load_bundle(torchaudio)
        model = self._load_model(bundle, torch)
        dictionary = {label: index for index, label in enumerate(bundle.get_labels())}

        if "|" not in dictionary:
            raise AlignmentUnavailableError(
                f"Forced aligner bundle '{self.bundle_name}' does not expose a word-boundary token"
            )

        transcript = "|" + "|".join(normalized for _, normalized in transcript_words) + "|"
        try:
            tokens = [dictionary[character] for character in transcript]
        except KeyError as exc:
            raise AlignmentError(
                f"Forced aligner transcript contains unsupported character: {exc.args[0]!r}"
            ) from exc

        waveform = self._pcm_bytes_to_waveform(
            torch=torch,
            torchaudio=torchaudio,
            pcm_bytes=pcm_bytes,
            sample_rate=sample_rate,
            channels=channels,
            target_sample_rate=int(bundle.sample_rate),
        )

        with torch.inference_mode():
            emissions, _ = model(waveform)

        emission = torch.log_softmax(emissions[0], dim=-1).cpu()
        blank_id = dictionary.get("-", 0)
        trellis = self._get_trellis(torch, emission, tokens, blank_id)
        path = self._backtrack(torch, trellis, emission, tokens, blank_id)
        if not path:
            raise AlignmentError("Forced aligner could not find an alignment path for the transcript")

        label_segments = self._merge_repeats(path, transcript)
        word_segments = self._merge_words(label_segments)
        if len(word_segments) != len(transcript_words):
            raise AlignmentError(
                "Forced aligner produced a different number of aligned words than the normalized transcript"
            )

        seconds_per_frame = waveform.shape[1] / bundle.sample_rate / max(1, emission.shape[0])
        words: list[WordTimestamp] = []
        for index, ((original_word, _), segment) in enumerate(zip(transcript_words, word_segments)):
            if segment.score < self.min_word_score:
                raise AlignmentError(
                    f"Forced aligner rejected word '{original_word}' with low confidence score {segment.score:.3f}"
                )

            start = round(segment.start * seconds_per_frame, 4)
            end = round(segment.end * seconds_per_frame, 4)
            words.append(
                WordTimestamp(
                    word=original_word,
                    start=start,
                    end=max(start, end),
                    phoneme_indices=(),
                )
            )

        return AlignmentResult(
            phonemes=[],
            words=words,
            sample_rate=sample_rate,
        )

    def _build_transcript_words(self, text: str) -> list[tuple[str, str]]:
        words: list[tuple[str, str]] = []
        for raw_token in _NON_SPACE_RE.findall(text):
            normalized = _NORMALIZE_RE.sub("", raw_token.upper()).strip("'")
            if normalized:
                words.append((raw_token, normalized))
                continue

            if any(character.isalnum() for character in raw_token):
                raise AlignmentError(
                    f"Forced aligner currently supports English alphabetic words only; unsupported token: {raw_token!r}"
                )

        return words

    def _load_runtime(self):
        if self._torch is not None and self._torchaudio is not None:
            return self._torch, self._torchaudio

        try:
            import torch  # type: ignore
            import torchaudio  # type: ignore
        except ImportError as exc:
            raise AlignmentUnavailableError(
                "Forced CTC alignment requires both torch and torchaudio to be installed"
            ) from exc

        self._torch = torch
        self._torchaudio = torchaudio
        return torch, torchaudio

    def _load_bundle(self, torchaudio):
        if self._bundle is not None:
            return self._bundle

        try:
            bundle = getattr(torchaudio.pipelines, self.bundle_name)
        except AttributeError as exc:
            raise AlignmentUnavailableError(
                f"Unknown torchaudio forced-aligner bundle: {self.bundle_name}"
            ) from exc

        self._bundle = bundle
        return bundle

    def _load_model(self, bundle, torch):
        if self._model is not None:
            return self._model

        try:
            model = bundle.get_model().to(torch.device("cpu"))
        except Exception as exc:  # pragma: no cover - defensive around runtime model loading
            raise AlignmentUnavailableError(
                f"Unable to initialize forced aligner bundle '{self.bundle_name}': {exc}"
            ) from exc

        model.eval()
        self._model = model
        return model

    def _pcm_bytes_to_waveform(self, *, torch, torchaudio, pcm_bytes: bytes, sample_rate: int, channels: int, target_sample_rate: int):
        samples = array("h")
        samples.frombytes(pcm_bytes)
        if not samples:
            raise AlignmentError("Forced aligner received empty PCM audio")

        if channels > 1:
            mono = [samples[index] for index in range(0, len(samples), channels)]
        else:
            mono = list(samples)

        waveform = torch.tensor(mono, dtype=torch.float32).unsqueeze(0) / 32768.0
        if sample_rate != target_sample_rate:
            waveform = torchaudio.functional.resample(waveform, sample_rate, target_sample_rate)

        return waveform

    def _get_trellis(self, torch, emission, tokens: list[int], blank_id: int):
        num_frames = emission.size(0)
        num_tokens = len(tokens)
        if num_frames < num_tokens:
            raise AlignmentError("Forced aligner audio is too short for the provided transcript")

        trellis = torch.zeros((num_frames, num_tokens), device=emission.device)
        trellis[1:, 0] = torch.cumsum(emission[1:, blank_id], dim=0)
        trellis[0, 1:] = -float("inf")
        trellis[-num_tokens + 1 :, 0] = float("inf")

        for frame_index in range(num_frames - 1):
            trellis[frame_index + 1, 1:] = torch.maximum(
                trellis[frame_index, 1:] + emission[frame_index, blank_id],
                trellis[frame_index, :-1] + emission[frame_index, tokens[1:]],
            )

        return trellis

    def _backtrack(self, torch, trellis, emission, tokens: list[int], blank_id: int) -> list[_Point]:
        token_index = trellis.size(1) - 1
        time_index = int(torch.argmax(trellis[:, token_index]).item())
        path: list[_Point] = [_Point(token_index=token_index, time_index=time_index, score=emission[time_index, blank_id].exp().item())]

        while token_index > 0:
            if time_index <= 0:
                raise AlignmentError("Forced aligner backtracking failed before consuming the transcript")

            stay_score = trellis[time_index - 1, token_index] + emission[time_index - 1, blank_id]
            change_score = trellis[time_index - 1, token_index - 1] + emission[time_index - 1, tokens[token_index]]
            time_index -= 1

            if change_score > stay_score:
                token_index -= 1
                probability = emission[time_index, tokens[token_index + 1]].exp().item()
            else:
                probability = emission[time_index, blank_id].exp().item()

            path.append(_Point(token_index=token_index, time_index=time_index, score=probability))

        while time_index > 0:
            probability = emission[time_index - 1, blank_id].exp().item()
            path.append(_Point(token_index=0, time_index=time_index - 1, score=probability))
            time_index -= 1

        return list(reversed(path))

    def _merge_repeats(self, path: list[_Point], transcript: str) -> list[_Segment]:
        segments: list[_Segment] = []
        start_index = 0
        while start_index < len(path):
            end_index = start_index + 1
            while end_index < len(path) and path[start_index].token_index == path[end_index].token_index:
                end_index += 1

            score = sum(point.score for point in path[start_index:end_index]) / (end_index - start_index)
            segments.append(
                _Segment(
                    label=transcript[path[start_index].token_index],
                    start=path[start_index].time_index,
                    end=path[end_index - 1].time_index + 1,
                    score=score,
                )
            )
            start_index = end_index

        return segments

    def _merge_words(self, segments: list[_Segment], separator: str = "|") -> list[_Segment]:
        words: list[_Segment] = []
        start_index = 0
        end_index = 0

        while start_index < len(segments):
            if end_index >= len(segments) or segments[end_index].label == separator:
                if start_index != end_index:
                    grouped_segments = segments[start_index:end_index]
                    score = sum(segment.score * segment.length for segment in grouped_segments) / sum(
                        segment.length for segment in grouped_segments
                    )
                    words.append(
                        _Segment(
                            label="".join(segment.label for segment in grouped_segments),
                            start=grouped_segments[0].start,
                            end=grouped_segments[-1].end,
                            score=score,
                        )
                    )

                start_index = end_index + 1
                end_index = start_index
                continue

            end_index += 1

        return words


__all__ = ["ForcedCtcAlignmentEngine"]