"""Small WAV helpers used by adapters and the desktop runner."""

from pathlib import Path
import wave

from .domain import AudioFormat
from .errors import InvalidAudioError


def inspect_wav(path: Path) -> tuple:
    if not path.is_file():
        raise InvalidAudioError("input WAV does not exist: %s" % path)
    try:
        with wave.open(str(path), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            audio_format = AudioFormat(
                sample_rate=sample_rate,
                channels=wav_file.getnchannels(),
                sample_width=wav_file.getsampwidth(),
            )
    except (wave.Error, EOFError) as exc:
        raise InvalidAudioError("unsupported or invalid WAV: %s" % path) from exc
    if sample_rate <= 0:
        raise InvalidAudioError("WAV sample rate must be positive")
    return int(frame_count * 1000 / sample_rate), audio_format


def read_wav_pcm(path: Path) -> tuple:
    try:
        with wave.open(str(path), "rb") as wav_file:
            audio_format = AudioFormat(
                sample_rate=wav_file.getframerate(),
                channels=wav_file.getnchannels(),
                sample_width=wav_file.getsampwidth(),
            )
            return wav_file.readframes(wav_file.getnframes()), audio_format
    except (wave.Error, EOFError) as exc:
        raise InvalidAudioError("unsupported or invalid WAV: %s" % path) from exc


def write_wav(path: Path, pcm: bytes, audio_format: AudioFormat) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(audio_format.channels)
        wav_file.setsampwidth(audio_format.sample_width)
        wav_file.setframerate(audio_format.sample_rate)
        wav_file.writeframes(pcm)

