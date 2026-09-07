"""Codec-neutral bridge from terminal turns to voice orchestration."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Protocol, Sequence, Tuple

from .audio import write_wav
from .domain import AudioFormat
from .errors import TerminalAudioBridgeError, TerminalProtocolError, TurnCancelledError
from .orchestrator import TurnOrchestrator
from .terminal_protocol import (
    AudioParameters,
    DOWNLINK_AUDIO,
    UPLINK_AUDIO,
    validate_binary_frame,
)
from .terminal_transport import TerminalTurnRequest, TerminalTurnResponse


UPLINK_PCM = AudioFormat(
    sample_rate=UPLINK_AUDIO.sample_rate,
    channels=UPLINK_AUDIO.channels,
    sample_width=2,
    encoding="pcm_s16le",
)
DEFAULT_TERMINAL_EMOTION = "neutral"


@dataclass(frozen=True)
class DecodedTerminalAudio:
    pcm: bytes
    audio_format: AudioFormat


class TerminalAudioCodec(Protocol):
    async def decode_uplink(
        self,
        frames: Sequence[bytes],
        source: AudioParameters,
    ) -> DecodedTerminalAudio:
        ...

    async def encode_downlink(
        self,
        pcm: bytes,
        source: AudioFormat,
        target: AudioParameters,
    ) -> Sequence[bytes]:
        ...


class OrchestratorTerminalBridge:
    def __init__(
        self,
        orchestrator: TurnOrchestrator,
        codec: TerminalAudioCodec,
    ) -> None:
        self._orchestrator = orchestrator
        self._codec = codec

    async def __call__(self, request: TerminalTurnRequest) -> TerminalTurnResponse:
        if not request.audio_frames:
            raise TerminalAudioBridgeError("terminal uplink audio is empty")

        try:
            decoded = await self._codec.decode_uplink(
                request.audio_frames, UPLINK_AUDIO
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise TerminalAudioBridgeError("terminal uplink decode failed") from exc
        self._validate_decoded(decoded)

        with tempfile.TemporaryDirectory(prefix="dolls-terminal-turn-") as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            try:
                write_wav(input_path, decoded.pcm, decoded.audio_format)
            except Exception as exc:
                raise TerminalAudioBridgeError(
                    "terminal temporary WAV creation failed"
                ) from exc

            try:
                result = await self._orchestrator.run_turn(
                    input_path, session_id=request.session_id
                )
            except TurnCancelledError as exc:
                raise asyncio.CancelledError() from exc

            try:
                encoded = await self._codec.encode_downlink(
                    result.audio,
                    result.audio_format,
                    DOWNLINK_AUDIO,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise TerminalAudioBridgeError(
                    "terminal downlink encode failed"
                ) from exc

            frames = self._validate_encoded(encoded)
            return TerminalTurnResponse(
                transcript=result.transcript,
                reply_text=result.reply_text,
                emotion=DEFAULT_TERMINAL_EMOTION,
                audio_frames=frames,
            )

    @staticmethod
    def _validate_decoded(decoded: DecodedTerminalAudio) -> None:
        if not isinstance(decoded, DecodedTerminalAudio):
            raise TerminalAudioBridgeError("terminal decoded audio is invalid")
        if decoded.audio_format != UPLINK_PCM:
            raise TerminalAudioBridgeError("terminal decoded audio format is invalid")
        if not isinstance(decoded.pcm, bytes) or not decoded.pcm:
            raise TerminalAudioBridgeError("terminal decoded audio is empty")
        frame_width = decoded.audio_format.channels * decoded.audio_format.sample_width
        if len(decoded.pcm) % frame_width:
            raise TerminalAudioBridgeError("terminal decoded PCM is incomplete")

    @staticmethod
    def _validate_encoded(frames: Sequence[bytes]) -> Tuple[bytes, ...]:
        if isinstance(frames, (bytes, bytearray, str)):
            raise TerminalAudioBridgeError("terminal encoded audio frames are invalid")
        try:
            normalized = tuple(frames)
        except (TypeError, ValueError) as exc:
            raise TerminalAudioBridgeError(
                "terminal encoded audio frames are invalid"
            ) from exc
        if not normalized:
            raise TerminalAudioBridgeError("terminal encoded audio is empty")
        try:
            return tuple(validate_binary_frame(frame) for frame in normalized)
        except TerminalProtocolError as exc:
            raise TerminalAudioBridgeError(
                "terminal encoded audio frame is invalid"
            ) from exc
