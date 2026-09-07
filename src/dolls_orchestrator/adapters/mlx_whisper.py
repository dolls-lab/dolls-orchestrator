"""Optional Apple Silicon MLX Whisper speech-recognition adapter."""

import asyncio
import audioop
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Optional
import wave

from ..audio import inspect_wav
from ..domain import ASRResult, TurnContext
from ..errors import ProviderConfigurationError, ProviderUnavailableError


WhisperRunner = Callable[[Path, str], Mapping[str, Any]]


def _load_wav_for_whisper(audio_path: Path):
    try:
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise ProviderConfigurationError(
            "NumPy is required by the MLX Whisper adapter", stage="asr"
        ) from exc
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            if wav_file.getcomptype() != "NONE":
                raise ProviderConfigurationError(
                    "MLX Whisper input must be uncompressed PCM WAV", stage="asr"
                )
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            pcm = wav_file.readframes(wav_file.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ProviderConfigurationError(
            "MLX Whisper input is not a supported WAV", stage="asr"
        ) from exc
    if channels == 2:
        pcm = audioop.tomono(pcm, sample_width, 0.5, 0.5)
    elif channels != 1:
        raise ProviderConfigurationError(
            "MLX Whisper supports mono or stereo WAV input", stage="asr"
        )
    if sample_width != 2:
        pcm = audioop.lin2lin(pcm, sample_width, 2)
    if sample_rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, sample_rate, 16000, None)
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


def _default_runner(audio_path: Path, model: str) -> Mapping[str, Any]:
    try:
        import mlx_whisper  # type: ignore
    except ImportError as exc:
        raise ProviderConfigurationError(
            "MLX Whisper is not installed; install the optional mlx dependencies first",
            stage="asr",
        ) from exc
    audio = _load_wav_for_whisper(audio_path)
    return mlx_whisper.transcribe(audio, path_or_hf_repo=model, language="zh")


class MLXWhisperAdapter:
    provider = "mlx-whisper"

    def __init__(self, model: str, runner: Optional[WhisperRunner] = None) -> None:
        self.model = model
        self.runner = runner or _default_runner

    async def transcribe(self, audio_path: Path, context: TurnContext) -> ASRResult:
        started = time.perf_counter()
        duration_ms, _ = inspect_wav(audio_path)
        try:
            result = await asyncio.to_thread(self.runner, audio_path, self.model)
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(str(exc), stage="asr") from exc
        text = str(result.get("text", "")).strip()
        if not text:
            raise ProviderUnavailableError("MLX Whisper returned no text", stage="asr")
        return ASRResult(
            text=text,
            language=str(result.get("language", "zh-CN")),
            duration_ms=duration_ms,
            confidence=None,
            provider=self.provider,
            model=self.model,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
