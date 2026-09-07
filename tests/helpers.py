from pathlib import Path
import wave


def write_silent_wav(path: Path, duration_ms: int = 100, sample_rate: int = 16000) -> None:
    frame_count = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0\0" * frame_count)

