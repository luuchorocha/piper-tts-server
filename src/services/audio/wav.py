import io
import wave
from dataclasses import dataclass


class WavFileError(ValueError):
    pass


@dataclass(frozen=True)
class PcmWavAudio:
    pcm_bytes: bytes
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int


def read_pcm_wav(wav_bytes: bytes) -> PcmWavAudio:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_reader:
            sample_rate = wav_reader.getframerate()
            channels = wav_reader.getnchannels()
            sample_width = wav_reader.getsampwidth()
            frame_count = wav_reader.getnframes()

            if sample_rate <= 0:
                raise WavFileError("audio WAV must include a valid sample rate")
            if channels <= 0:
                raise WavFileError("audio WAV must include at least one channel")
            if frame_count <= 0:
                raise WavFileError("audio WAV must contain audio frames")

            pcm_bytes = wav_reader.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise WavFileError("audio must be a readable WAV file") from exc

    if not pcm_bytes:
        raise WavFileError("audio WAV must contain audio frames")

    return PcmWavAudio(
        pcm_bytes=pcm_bytes,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        frame_count=frame_count,
    )
