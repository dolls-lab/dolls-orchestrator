"""Temporary TTS adapter backed by macOS say and afconvert."""

import asyncio
from pathlib import Path
import shutil
import tempfile
import time
from typing import AsyncIterator, Awaitable, Callable, Optional, Sequence

from ..audio import read_wav_pcm
from ..domain import AudioChunk, SynthesisRequest
from ..errors import ProviderConfigurationError, ProviderUnavailableError


CommandRunner = Callable[[Sequence[str]], Awaitable[None]]


async def _run_command(command: Sequence[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await process.communicate()
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise
    if process.returncode:
        raise ProviderUnavailableError(
            "%s failed: %s" % (command[0], stderr.decode("utf-8", "replace").strip()),
            stage="tts",
        )


class MacOSSayTTSAdapter:
    provider = "macos-say"
    model = "system-voice"

    def __init__(
        self,
        voice: str = "Tingting",
        sample_rate: int = 24000,
        command_runner: Optional[CommandRunner] = None,
    ) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.command_runner = command_runner or _run_command

    def _check_commands(self) -> None:
        if self.command_runner is not _run_command:
            return
        for name in ("say", "afconvert"):
            if shutil.which(name) is None:
                raise ProviderConfigurationError(
                    "%s is required for the macOS TTS profile" % name,
                    stage="tts",
                )

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        self._check_commands()
        if not request.text.strip():
            raise ProviderUnavailableError("TTS text must not be empty", stage="tts")
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="dolls-tts-") as temp_dir:
            aiff_path = Path(temp_dir) / "speech.aiff"
            wav_path = Path(temp_dir) / "speech.wav"
            rate = max(80, min(450, int(200 * request.speed)))
            await self.command_runner(
                ["say", "-v", self.voice, "-r", str(rate), "-o", str(aiff_path), request.text]
            )
            await self.command_runner(
                [
                    "afconvert",
                    "-f",
                    "WAVE",
                    "-d",
                    "LEI16@%d" % self.sample_rate,
                    "-c",
                    "1",
                    str(aiff_path),
                    str(wav_path),
                ]
            )
            pcm, audio_format = read_wav_pcm(wav_path)
            if not pcm:
                raise ProviderUnavailableError(
                    "macOS TTS produced an empty audio file", stage="tts"
                )
        yield AudioChunk(
            data=pcm,
            sequence=request.sequence,
            audio_format=audio_format,
            provider=self.provider,
            model="%s:%s" % (self.model, self.voice),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
