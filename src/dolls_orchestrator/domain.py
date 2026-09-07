"""Provider-independent orchestration types and contracts."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Protocol, Sequence


@dataclass(frozen=True)
class TurnContext:
    session_id: str
    turn_id: str
    generation_id: str


@dataclass(frozen=True)
class AudioFormat:
    sample_rate: int
    channels: int = 1
    sample_width: int = 2
    encoding: str = "pcm_s16le"


@dataclass(frozen=True)
class ASRResult:
    text: str
    language: str
    duration_ms: int
    confidence: Optional[float]
    provider: str
    model: str
    elapsed_ms: float


@dataclass(frozen=True)
class LLMEvent:
    kind: str
    text: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Mapping[str, int] = field(default_factory=dict)
    elapsed_ms: Optional[float] = None


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    language: str
    voice_id: str
    sequence: int
    context: TurnContext
    emotion: Optional[str] = None
    speed: float = 1.0


@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    sequence: int
    audio_format: AudioFormat
    provider: str
    model: str
    elapsed_ms: float


@dataclass
class StageTelemetry:
    provider: str = ""
    model: str = ""
    elapsed_ms: float = 0.0
    first_output_ms: Optional[float] = None
    usage: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterHealth:
    stage: str
    provider: str
    model: str
    status: str
    reason: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass
class TurnTelemetry:
    session_id: str
    turn_id: str
    generation_id: str
    character_id: str = ""
    character_version: str = ""
    status: str = "running"
    first_audio_ms: Optional[float] = None
    total_ms: float = 0.0
    stages: Dict[str, StageTelemetry] = field(default_factory=dict)
    error_stage: Optional[str] = None
    error_type: Optional[str] = None
    states: List[str] = field(default_factory=lambda: ["input_ready"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "generation_id": self.generation_id,
            "character_id": self.character_id,
            "character_version": self.character_version,
            "status": self.status,
            "first_audio_ms": (
                round(self.first_audio_ms, 3)
                if self.first_audio_ms is not None
                else None
            ),
            "total_ms": round(self.total_ms, 3),
            "stages": {
                name: {
                    "provider": stage.provider,
                    "model": stage.model,
                    "elapsed_ms": round(stage.elapsed_ms, 3),
                    "first_output_ms": (
                        round(stage.first_output_ms, 3)
                        if stage.first_output_ms is not None
                        else None
                    ),
                    "usage": dict(stage.usage),
                }
                for name, stage in self.stages.items()
            },
            "error_stage": self.error_stage,
            "error_type": self.error_type,
            "states": list(self.states),
        }


@dataclass(frozen=True)
class TurnResult:
    context: TurnContext
    transcript: str
    reply_text: str
    audio: bytes
    audio_format: AudioFormat
    telemetry: TurnTelemetry


class ASRAdapter(Protocol):
    def health(self) -> AdapterHealth:
        ...

    async def transcribe(self, audio_path: Path, context: TurnContext) -> ASRResult:
        ...


class LLMAdapter(Protocol):
    def health(self) -> AdapterHealth:
        ...

    def stream_reply(
        self, messages: Sequence[Mapping[str, str]], context: TurnContext
    ) -> AsyncIterator[LLMEvent]:
        ...


class TTSAdapter(Protocol):
    def health(self) -> AdapterHealth:
        ...

    def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        ...
