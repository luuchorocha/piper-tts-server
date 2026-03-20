import gc
import logging
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

import onnxruntime
from piper import PiperVoice
from piper.download_voices import download_voice

from src.core.constants import DOWNLOAD_COOLDOWN_SECS
from src.managers.voices.loader import load_voice

LOGGER = logging.getLogger(__name__)


class VoiceDownloadError(RuntimeError):
    pass


class VoiceDownloadBusyError(VoiceDownloadError):
    pass


class VoiceDownloadsDisabledError(VoiceDownloadError):
    pass


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
        self.default_model_path = default_model_path
        self.default_model_id = default_model_id
        self.use_cuda = use_cuda
        self.session_options = session_options
        self.max_loaded_voices = max_loaded_voices
        self.download_dir = download_dir
        self.allow_downloads = allow_downloads
        self._loaded: OrderedDict[str, PiperVoice] = OrderedDict()
        self._lock = threading.Lock()
        self._download_lock = threading.Lock()
        self._default_probe_lock = threading.Lock()
        self._default_probe_key: tuple[str, int, int] | None = None
        self._default_probe_error: str | None = None
        self._last_download_at = 0.0

    def _path_for(self, model_id: str) -> Optional[Path]:
        if (
            model_id == self.default_model_id
            and self.default_model_path is not None
            and self.default_model_path.exists()
        ):
            return self.default_model_path

        for data_dir in self.data_dirs:
            candidate = data_dir / f"{model_id}.onnx"
            if candidate.exists():
                return candidate
        return None

    def _remember_default_path(self, model_id: str, model_path: Path) -> None:
        if model_id == self.default_model_id:
            self.default_model_path = model_path

    def _discard_cached_voice(self, model_id: str) -> None:
        with self._lock:
            cached = self._loaded.pop(model_id, None)

        if cached is not None:
            LOGGER.info("Discarding cached voice: %s", model_id)
            self._release_voice(cached)

    @staticmethod
    def _release_voice(voice: PiperVoice) -> None:
        try:
            del voice.session
            del voice
        except AttributeError:
            pass
        finally:
            gc.collect()

    @staticmethod
    def _probe_key_for(model_path: Path) -> tuple[str, int, int]:
        config_path = Path(f"{model_path}.json")
        model_mtime = model_path.stat().st_mtime_ns if model_path.exists() else -1
        config_mtime = config_path.stat().st_mtime_ns if config_path.exists() else -1
        return (str(model_path), model_mtime, config_mtime)

    def download(
        self,
        model_id: str,
        *,
        force_redownload: bool = False,
        enforce_cooldown: bool = False,
    ) -> Path:
        if not self.allow_downloads:
            raise VoiceDownloadsDisabledError("voice downloads disabled")

        if not self._download_lock.acquire(blocking=False):
            LOGGER.warning(
                "[download] rejected voice=%s - another download in progress",
                model_id,
            )
            raise VoiceDownloadBusyError("A download is already in progress")

        try:
            if enforce_cooldown:
                elapsed = time.monotonic() - self._last_download_at
                if elapsed < DOWNLOAD_COOLDOWN_SECS:
                    LOGGER.warning("[download] rate limited voice=%s", model_id)
                    raise VoiceDownloadBusyError(
                        "Download rate limited, try again later",
                    )

            LOGGER.info("[download] start voice=%s force=%s", model_id, force_redownload)
            download_voice(
                model_id,
                self.download_dir,
                force_redownload=force_redownload,
            )

            model_path = self._path_for(model_id)
            if model_path is None:
                raise VoiceDownloadError(
                    f"Voice downloaded but files are still missing: {model_id}",
                )

            self._remember_default_path(model_id, model_path)
            self._discard_cached_voice(model_id)
            self._last_download_at = time.monotonic()
            LOGGER.info("[download] done voice=%s", model_id)
            return model_path
        except VoiceDownloadError:
            raise
        except Exception as exc:
            LOGGER.exception("[download] failed voice=%s", model_id)
            raise VoiceDownloadError(
                f"Failed to download voice: {model_id}",
            ) from exc
        finally:
            self._download_lock.release()

    def _ensure_model_path(self, model_id: str) -> Optional[Path]:
        model_path = self._path_for(model_id)
        if model_path is not None:
            self._remember_default_path(model_id, model_path)
            return model_path

        if not self.allow_downloads:
            return None

        try:
            LOGGER.info(
                "Voice not found locally: %s - downloading on demand",
                model_id,
            )
            return self.download(model_id)
        except VoiceDownloadsDisabledError:
            return None
        except VoiceDownloadError as exc:
            LOGGER.warning(
                "Unable to auto-download voice %s: %s",
                model_id,
                exc,
            )
            return self._path_for(model_id)

    def probe_default_voice(self) -> Tuple[bool, Optional[str]]:
        with self._lock:
            if self.default_model_id in self._loaded:
                return True, None

        model_path = self._path_for(self.default_model_id)
        if model_path is None:
            self.default_model_path = None
            return (
                False,
                f"Default voice is not available locally: {self.default_model_id}",
            )

        self._remember_default_path(self.default_model_id, model_path)

        with self._default_probe_lock:
            probe_key = self._probe_key_for(model_path)
            if probe_key == self._default_probe_key:
                return self._default_probe_error is None, self._default_probe_error

            config_path = Path(f"{model_path}.json")
            if not config_path.exists():
                error = f"Voice config is missing for default voice: {self.default_model_id}"
                self._default_probe_key = probe_key
                self._default_probe_error = error
                return False, error

            try:
                voice = load_voice(
                    model_path,
                    use_cuda=self.use_cuda,
                    session_options=self.session_options,
                    download_dir=self.download_dir,
                )
                self._release_voice(voice)
            except Exception:
                LOGGER.exception(
                    "Default voice readiness probe failed for %s",
                    self.default_model_id,
                )
                error = f"Default voice is not loadable: {self.default_model_id}"
                self._default_probe_key = probe_key
                self._default_probe_error = error
                return False, error

            self._default_probe_key = probe_key
            self._default_probe_error = None
            return True, None

    def get(self, requested_model_id: str) -> Tuple[PiperVoice, bool]:
        """Return (voice, is_ephemeral). Caller must release ephemeral voices."""
        model_id = requested_model_id or self.default_model_id
        model_path = self._ensure_model_path(model_id)
        if model_path is None and model_id != self.default_model_id:
            LOGGER.warning("Voice not found: %s - falling back to default", model_id)
            model_id = self.default_model_id
            model_path = self._ensure_model_path(model_id) or self.default_model_path
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
