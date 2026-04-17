import logging
import threading
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple

import onnxruntime
from piper import PiperVoice

from src.managers.voices.catalog import VoiceCatalog
from src.managers.voices.errors import (
    VoiceDownloadBusyError,
    VoiceDownloadError,
    VoiceDownloadsDisabledError,
)
from src.managers.voices.loader import load_voice, unload_voice

LOGGER = logging.getLogger(__name__)


class VoiceManager:
    """Thread-safe voice loader with optional LRU cache and lazy downloads.

    Cached voices are refcounted so an in-flight synthesis is never handed a
    handle whose ONNX session is freed by a concurrent download or LRU
    eviction. Evictions and discards on busy voices are deferred until the
    last lease is released.
    """

    def __init__(
        self,
        *,
        data_dirs: list[Path],
        default_model_id: str,
        default_model_path: Optional[Path],
        use_cuda: bool,
        session_options: onnxruntime.SessionOptions,
        max_loaded_voices: int,
        download_dir: Path,
        allow_downloads: bool,
    ) -> None:
        self.data_dirs = data_dirs
        self.use_cuda = use_cuda
        self.session_options = session_options
        self.max_loaded_voices = max_loaded_voices
        self.catalog = VoiceCatalog(
            data_dirs=data_dirs,
            default_model_id=default_model_id,
            default_model_path=default_model_path,
            use_cuda=use_cuda,
            session_options=session_options,
            download_dir=download_dir,
            allow_downloads=allow_downloads,
        )
        self._loaded: OrderedDict[str, PiperVoice] = OrderedDict()
        self._refcounts: dict[str, int] = {}
        self._pending_eviction: set[str] = set()
        self._lock = threading.Lock()

    @property
    def default_model_id(self) -> str:
        return self.catalog.default_model_id

    @property
    def default_model_path(self) -> Optional[Path]:
        return self.catalog.default_model_path

    @property
    def download_dir(self) -> Path:
        return self.catalog.download_dir

    @property
    def allow_downloads(self) -> bool:
        return self.catalog.allow_downloads

    @staticmethod
    def _release_voice(voice: PiperVoice) -> None:
        unload_voice(voice)

    def _take_for_release_locked(self, model_id: str) -> Optional[PiperVoice]:
        """Remove and return a cache entry; caller must release outside the lock."""
        voice = self._loaded.pop(model_id, None)
        self._refcounts.pop(model_id, None)
        self._pending_eviction.discard(model_id)
        return voice

    def _mark_or_evict_locked(self, model_id: str) -> Optional[PiperVoice]:
        if self._refcounts.get(model_id, 0) > 0:
            self._pending_eviction.add(model_id)
            return None

        return self._take_for_release_locked(model_id)

    def _enforce_capacity_locked(self) -> list[PiperVoice]:
        released: list[PiperVoice] = []
        while len(self._loaded) > self.max_loaded_voices:
            victim_id: Optional[str] = None
            for candidate_id in self._loaded:
                if self._refcounts.get(candidate_id, 0) == 0:
                    victim_id = candidate_id
                    break

            if victim_id is None:
                # Everything is in use — mark the LRU entry so it's evicted
                # as soon as its last lease is released.
                oldest = next(iter(self._loaded))
                self._pending_eviction.add(oldest)
                break

            voice = self._take_for_release_locked(victim_id)
            if voice is not None:
                LOGGER.info("Evicting cached voice: %s", victim_id)
                released.append(voice)

        return released

    def download(
        self,
        model_id: str,
        *,
        force_redownload: bool = False,
        enforce_cooldown: bool = False,
    ) -> Path:
        model_path = self.catalog.download(
            model_id,
            force_redownload=force_redownload,
            enforce_cooldown=enforce_cooldown,
        )
        with self._lock:
            voice = self._mark_or_evict_locked(model_id)
        if voice is not None:
            LOGGER.info("Discarding cached voice: %s", model_id)
            self._release_voice(voice)
        return model_path

    def probe_default_voice(self) -> Tuple[bool, Optional[str]]:
        with self._lock:
            is_loaded = self.default_model_id in self._loaded

        return self.catalog.probe_default_voice(is_loaded=is_loaded)

    def get(self, requested_model_id: str) -> Tuple[PiperVoice, str, bool]:
        """Return ``(voice, lease_id, is_ephemeral)``.

        Callers MUST call :meth:`release` with the returned tuple when done,
        typically via :meth:`lease`.
        """
        model_id = requested_model_id or self.default_model_id
        model_path = self.catalog.ensure_available(model_id)
        if model_path is None and model_id != self.default_model_id:
            LOGGER.warning("Voice not found: %s - falling back to default", model_id)
            model_id = self.default_model_id
            model_path = self.catalog.ensure_available(model_id) or self.default_model_path
        elif model_path is None:
            model_path = self.default_model_path

        if model_path is None:
            raise ValueError(f"Voice not available: {model_id}")

        if self.max_loaded_voices == 0:
            voice = load_voice(
                model_path,
                use_cuda=self.use_cuda,
                session_options=self.session_options,
                download_dir=self.download_dir,
            )
            return voice, model_id, True

        evicted: list[PiperVoice] = []
        try:
            with self._lock:
                cached = self._loaded.get(model_id)
                if cached is not None:
                    self._loaded.move_to_end(model_id)
                    self._refcounts[model_id] = self._refcounts.get(model_id, 0) + 1
                    return cached, model_id, False

                LOGGER.debug("Loading voice model: %s", model_id)
                voice = load_voice(
                    model_path,
                    use_cuda=self.use_cuda,
                    session_options=self.session_options,
                    download_dir=self.download_dir,
                )
                self._loaded[model_id] = voice
                self._loaded.move_to_end(model_id)
                self._refcounts[model_id] = 1
                evicted = self._enforce_capacity_locked()
                return voice, model_id, False
        finally:
            for old_voice in evicted:
                self._release_voice(old_voice)

    def release(self, voice: PiperVoice, lease_id: str, is_ephemeral: bool) -> None:
        if is_ephemeral:
            self._release_voice(voice)
            return

        to_release: Optional[PiperVoice] = None
        with self._lock:
            count = self._refcounts.get(lease_id, 0) - 1
            if count > 0:
                self._refcounts[lease_id] = count
            else:
                self._refcounts.pop(lease_id, None)
                should_evict = (
                    lease_id in self._pending_eviction
                    or len(self._loaded) > self.max_loaded_voices
                )
                if should_evict:
                    to_release = self._take_for_release_locked(lease_id)

        if to_release is not None:
            LOGGER.info("Releasing cached voice: %s", lease_id)
            self._release_voice(to_release)

    @contextmanager
    def lease(self, requested_model_id: str) -> Iterator[PiperVoice]:
        voice, lease_id, is_ephemeral = self.get(requested_model_id)
        try:
            yield voice
        finally:
            self.release(voice, lease_id, is_ephemeral)

    def clear_cache(self) -> None:
        with self._lock:
            loaded = list(self._loaded.items())
            self._loaded.clear()
            self._refcounts.clear()
            self._pending_eviction.clear()

        for model_id, voice in loaded:
            LOGGER.info("Releasing cached voice: %s", model_id)
            self._release_voice(voice)

    @classmethod
    def release_ephemeral(cls, voice: PiperVoice) -> None:
        cls._release_voice(voice)


__all__ = [
    "VoiceManager",
    "VoiceDownloadError",
    "VoiceDownloadBusyError",
    "VoiceDownloadsDisabledError",
]
