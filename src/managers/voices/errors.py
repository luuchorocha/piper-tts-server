class VoiceDownloadError(RuntimeError):
    pass


class VoiceDownloadBusyError(VoiceDownloadError):
    pass


class VoiceDownloadsDisabledError(VoiceDownloadError):
    pass


__all__ = [
    "VoiceDownloadError",
    "VoiceDownloadBusyError",
    "VoiceDownloadsDisabledError",
]