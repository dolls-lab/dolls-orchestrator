"""Deterministic adapters for tests and credential-free smoke runs."""

import asyncio
from array import array
import math
from pathlib import Path
import time
from typing import AsyncIterator, Mapping, Sequence

from ..audio import inspect_wav
from ..domain import (
    ASRResult,
    AudioChunk,
    AudioFormat,
    LLMEvent,
    SynthesisRequest,
    TurnContext,
)


class OfflineASRAdapter:
    provider = "offline"
    model = "fixed-transcript-v1"

    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    async def transcribe(self, audio_path: Path, context: TurnContext) -> ASRResult:
        started = time.perf_counter()
        duration_ms, _ = inspect_wav(audio_path)
        await asyncio.sleep(0)
        return ASRResult(
            text=self.transcript,
            language="zh-CN",
            duration_ms=duration_ms,
            confidence=None,
            provider=self.provider,
            model=self.model,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class OfflineLLMAdapter:
    provider = "offline"
    model = "scripted-character-v1"

    def __init__(self, reply: str, chunk_chars: int = 4, delay_seconds: float = 0) -> None:
        self.reply = reply
        self.chunk_chars = max(1, chunk_chars)
        self.delay_seconds = max(0.0, delay_seconds)

    async def stream_reply(
        self, messages: Sequence[Mapping[str, str]], context: TurnContext
    ) -> AsyncIterator[LLMEvent]:
        active_elapsed = 0.0
        for index in range(0, len(self.reply), self.chunk_chars):
            active_started = time.perf_counter()
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            else:
                await asyncio.sleep(0)
            active_elapsed += time.perf_counter() - active_started
            yield LLMEvent(kind="text_delta", text=self.reply[index : index + self.chunk_chars])
        yield LLMEvent(
            kind="completed",
            provider=self.provider,
            model=self.model,
            usage={"input_messages": len(messages), "output_characters": len(self.reply)},
            elapsed_ms=active_elapsed * 1000,
        )


class ToneTTSAdapter:
    provider = "offline"
    model = "pcm-tone-v1"

    def __init__(self, sample_rate: int = 24000) -> None:
        self.audio_format = AudioFormat(sample_rate=sample_rate)

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        started = time.perf_counter()
        duration_seconds = max(0.12, min(1.2, len(request.text) * 0.025))
        sample_count = int(self.audio_format.sample_rate * duration_seconds)
        frequency = 440 + (request.sequence % 4) * 55
        amplitude = 5000
        samples = array(
            "h",
            (
                int(amplitude * math.sin(2 * math.pi * frequency * i / self.audio_format.sample_rate))
                for i in range(sample_count)
            ),
        )
        await asyncio.sleep(0)
        yield AudioChunk(
            data=samples.tobytes(),
            sequence=request.sequence,
            audio_format=self.audio_format,
            provider=self.provider,
            model=self.model,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
