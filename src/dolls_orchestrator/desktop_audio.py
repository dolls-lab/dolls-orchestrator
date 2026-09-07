"""Injectable desktop microphone recording and WAV playback."""

import asyncio
from pathlib import Path
import shutil
from typing import Any, Awaitable, List, Optional, Protocol, Union

from .audio import write_wav
from .domain import AudioFormat
from .errors import MicrophoneError, PlaybackError


class Recorder(Protocol):
    async def record_until(self, output_path: Path, stop_signal: Awaitable[Any]) -> None:
        ...


class Player(Protocol):
    async def play(self, audio_path: Path) -> None:
        ...


class SoundDeviceRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        device: Optional[Union[int, str]] = None,
        sounddevice_module=None,
    ) -> None:
        self.sample_rate = sample_rate
        self.device = device
        self._sounddevice_module = sounddevice_module

    def _sounddevice(self):
        if self._sounddevice_module is not None:
            return self._sounddevice_module
        try:
            import sounddevice  # type: ignore
        except ImportError as exc:
            raise MicrophoneError(
                "sounddevice is not installed; install the desktop optional dependency"
            ) from exc
        return sounddevice

    def list_devices(self) -> str:
        try:
            return str(self._sounddevice().query_devices())
        except Exception as exc:
            raise MicrophoneError(
                "unable to list microphones; check macOS microphone permission: %s" % exc
            ) from exc

    async def record_until(self, output_path: Path, stop_signal: Awaitable[Any]) -> None:
        frames: List[bytes] = []

        def callback(indata, frame_count, time_info, status) -> None:
            frames.append(bytes(indata))

        try:
            stream = self._sounddevice().RawInputStream(
                samplerate=self.sample_rate,
                blocksize=0,
                device=self.device,
                channels=1,
                dtype="int16",
                callback=callback,
            )
            stream.start()
        except Exception as exc:
            if isinstance(stop_signal, asyncio.Future):
                stop_signal.cancel()
            elif hasattr(stop_signal, "close"):
                stop_signal.close()
            raise MicrophoneError(
                "unable to start microphone; select a valid device and allow microphone access: %s"
                % exc
            ) from exc
        try:
            await stop_signal
        finally:
            try:
                stream.stop()
            finally:
                stream.close()
        pcm = b"".join(frames)
        if not pcm:
            raise MicrophoneError("microphone captured no audio frames")
        write_wav(output_path, pcm, AudioFormat(sample_rate=self.sample_rate))


class AfplayPlayer:
    def __init__(self, executable: str = "afplay", process_factory=None) -> None:
        self.executable = executable
        self.process_factory = process_factory or asyncio.create_subprocess_exec

    async def play(self, audio_path: Path) -> None:
        if self.process_factory is asyncio.create_subprocess_exec:
            resolved = shutil.which(self.executable)
            if resolved is None:
                raise PlaybackError("afplay is unavailable; use --no-playback")
        else:
            resolved = self.executable
        process = await self.process_factory(
            resolved,
            str(audio_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await process.communicate()
        except asyncio.CancelledError:
            process.terminate()
            await process.wait()
            raise
        if process.returncode:
            raise PlaybackError(
                "afplay failed: %s" % stderr.decode("utf-8", "replace").strip()
            )
