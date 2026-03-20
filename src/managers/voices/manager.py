import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

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
    """Thread-safe voice loader with optional LRU cache and lazy downloads."""

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

    def _discard_cached_voice(self, model_id: str) -> None:
        with self._lock:
            cached = self._loaded.pop(model_id, None)

        if cached is not None:
            LOGGER.info("Discarding cached voice: %s", model_id)
            self._release_voice(cached)

    @staticmethod
    def _release_voice(voice: PiperVoice) -> None:
        unload_voice(voice)

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
        self._discard_cached_voice(model_id)
        return model_path

    def probe_default_voice(self) -> Tuple[bool, Optional[str]]:
        with self._lock:
            is_loaded = self.default_model_id in self._loaded

        return self.catalog.probe_default_voice(is_loaded=is_loaded)

    def get(self, requested_model_id: str) -> Tuple[PiperVoice, bool]:
        """Return (voice, is_ephemeral). Caller must release ephemeral voices."""
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
            return (
                load_voice(
                    model_path,
                    use_cuda=self.use_cuda,
                    session_options=self.session_options,
                    download_dir=self.download_dir,
                ),
                True,
            )

        with self._lock:
            cached = self._loaded.get(model_id)
            if cached is not None:
                self._loaded.move_to_end(model_id)
                return cached, False

            LOGGER.debug("Loading voice model: %s", model_id)
            voice = load_voice(
                model_path,
                use_cuda=self.use_cuda,
                session_options=self.session_options,
                download_dir=self.download_dir,
            )
            self._loaded[model_id] = voice
            self._loaded.move_to_end(model_id)

            while len(self._loaded) > self.max_loaded_voices:
                evicted_id, evicted_voice = self._loaded.popitem(last=False)
                LOGGER.info("Evicting cached voice: %s", evicted_id)
                self._release_voice(evicted_voice)

            return voice, False

    def clear_cache(self) -> None:
        with self._lock:
            loaded = list(self._loaded.items())
            self._loaded.clear()

        for model_id, voice in loaded:
            LOGGER.info("Releasing cached voice: %s", model_id)
            self._release_voice(voice)

    @classmethod
    def release_ephemeral(cls, voice: PiperVoice) -> None:
        cls._release_voice(voice)
