"""Generation-aware voice turn orchestration."""

import asyncio
import time
from pathlib import Path
from typing import AsyncIterator, Callable, Dict, List, Mapping, Optional
from uuid import uuid4

from .config import Settings
from .domain import (
    ASRAdapter,
    AudioChunk,
    AudioFormat,
    LLMAdapter,
    LLMEvent,
    StageTelemetry,
    SynthesisRequest,
    TTSAdapter,
    TurnContext,
    TurnResult,
    TurnTelemetry,
)
from .errors import (
    OrchestratorError,
    ProviderUnavailableError,
    StageTimeoutError,
    StaleGenerationError,
    TurnCancelledError,
)
from .sentence import SentenceSplitter
from .session import ConversationStore


TelemetrySink = Callable[[TurnTelemetry], None]
StateSink = Callable[[str], None]


class TurnOrchestrator:
    CHARACTER_INSTRUCTION = (
        "你是三月七风格的对话角色。语气活泼、友善、简短；不知道时坦率说明，"
        "不要声称自己是真实人物。单次回答尽量控制在一百五十个汉字以内。"
    )

    def __init__(
        self,
        asr: ASRAdapter,
        llm: LLMAdapter,
        tts: TTSAdapter,
        settings: Settings,
        conversations: Optional[ConversationStore] = None,
        telemetry_sink: Optional[TelemetrySink] = None,
        state_sink: Optional[StateSink] = None,
    ) -> None:
        self.asr = asr
        self.llm = llm
        self.tts = tts
        self.settings = settings
        self.conversations = conversations or ConversationStore(settings.context_turns)
        self.telemetry_sink = telemetry_sink
        self.state_sink = state_sink
        self.last_telemetry: Optional[TurnTelemetry] = None
        self._active_generations: Dict[str, str] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def run_turn(self, audio_path: Path, session_id: str = "desktop") -> TurnResult:
        current_task = asyncio.current_task()
        assert current_task is not None
        previous_task = self._active_tasks.get(session_id)
        generation_id = str(uuid4())
        context = TurnContext(
            session_id=session_id,
            turn_id=str(uuid4()),
            generation_id=generation_id,
        )
        self._active_generations[session_id] = generation_id
        self._active_tasks[session_id] = current_task
        if previous_task is not None and previous_task is not current_task:
            previous_task.cancel()

        telemetry = TurnTelemetry(
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation_id=context.generation_id,
        )
        total_started = time.perf_counter()
        current_stage = "asr"
        try:
            self._transition(telemetry, "transcribing")
            asr_result = await self._with_timeout(
                self.asr.transcribe(audio_path, context),
                self.settings.asr_timeout_seconds,
                "asr",
            )
            self._ensure_current(context)
            telemetry.stages["asr"] = StageTelemetry(
                provider=asr_result.provider,
                model=asr_result.model,
                elapsed_ms=asr_result.elapsed_ms,
            )

            messages: List[Mapping[str, str]] = [
                {"role": "system", "content": self.CHARACTER_INSTRUCTION}
            ]
            messages.extend(self.conversations.messages(session_id))
            messages.append({"role": "user", "content": asr_result.text})

            current_stage = "llm"
            self._transition(telemetry, "generating")
            llm_started = time.perf_counter()
            llm_first_ms: Optional[float] = None
            reply_parts: List[str] = []
            pcm_parts: List[bytes] = []
            output_format: Optional[AudioFormat] = None
            tts_elapsed = 0.0
            tts_provider = ""
            tts_model = ""
            tts_first_ms: Optional[float] = None
            tts_started: Optional[float] = None
            sentence_sequence = 0
            splitter = SentenceSplitter(self.settings.sentence_max_chars)

            llm_iterator = self.llm.stream_reply(messages, context).__aiter__()
            while True:
                try:
                    event = await self._next_event(
                        llm_iterator, self.settings.llm_timeout_seconds, "llm"
                    )
                except StopAsyncIteration:
                    break
                self._ensure_current(context)
                if event.kind == "text_delta":
                    if llm_first_ms is None:
                        llm_first_ms = (time.perf_counter() - llm_started) * 1000
                    reply_parts.append(event.text)
                    for sentence in splitter.feed(event.text):
                        current_stage = "tts"
                        self._transition_once(telemetry, "synthesizing")
                        if tts_started is None:
                            tts_started = time.perf_counter()
                        chunks = await self._synthesize_sentence(
                            sentence, sentence_sequence, context
                        )
                        sentence_sequence += 1
                        for chunk in chunks:
                            if output_format is None:
                                output_format = chunk.audio_format
                                tts_first_ms = (time.perf_counter() - tts_started) * 1000
                            elif output_format != chunk.audio_format:
                                raise ProviderUnavailableError(
                                    "TTS changed audio format within a turn", stage="tts"
                                )
                            pcm_parts.append(chunk.data)
                            tts_elapsed += chunk.elapsed_ms
                            tts_provider = chunk.provider
                            tts_model = chunk.model
                    current_stage = "llm"
                elif event.kind == "completed":
                    telemetry.stages["llm"] = StageTelemetry(
                        provider=event.provider or "unknown",
                        model=event.model or "unknown",
                        elapsed_ms=event.elapsed_ms
                        if event.elapsed_ms is not None
                        else (time.perf_counter() - llm_started) * 1000,
                        first_output_ms=llm_first_ms,
                        usage=dict(event.usage),
                    )

            for sentence in splitter.finish():
                current_stage = "tts"
                self._transition_once(telemetry, "synthesizing")
                if tts_started is None:
                    tts_started = time.perf_counter()
                chunks = await self._synthesize_sentence(
                    sentence, sentence_sequence, context
                )
                for chunk in chunks:
                    if output_format is None:
                        output_format = chunk.audio_format
                        tts_first_ms = (time.perf_counter() - tts_started) * 1000
                    elif output_format != chunk.audio_format:
                        raise ProviderUnavailableError(
                            "TTS changed audio format within a turn", stage="tts"
                        )
                    pcm_parts.append(chunk.data)
                    tts_elapsed += chunk.elapsed_ms
                    tts_provider = chunk.provider
                    tts_model = chunk.model

            self._ensure_current(context)
            reply_text = "".join(reply_parts).strip()
            if not reply_text:
                raise ProviderUnavailableError("LLM returned no reply text", stage="llm")
            if output_format is None or not pcm_parts:
                raise ProviderUnavailableError("TTS returned no audio", stage="tts")
            if "llm" not in telemetry.stages:
                telemetry.stages["llm"] = StageTelemetry(
                    provider="unknown",
                    model="unknown",
                    elapsed_ms=(time.perf_counter() - llm_started) * 1000,
                    first_output_ms=llm_first_ms,
                )
            telemetry.stages["tts"] = StageTelemetry(
                provider=tts_provider,
                model=tts_model,
                elapsed_ms=tts_elapsed,
                first_output_ms=tts_first_ms,
            )
            self.conversations.commit(session_id, asr_result.text, reply_text)
            self._transition(telemetry, "completed")
            telemetry.status = "completed"
            telemetry.total_ms = (time.perf_counter() - total_started) * 1000
            self._publish_telemetry(telemetry)
            return TurnResult(
                context=context,
                transcript=asr_result.text,
                reply_text=reply_text,
                audio=b"".join(pcm_parts),
                audio_format=output_format,
                telemetry=telemetry,
            )
        except asyncio.CancelledError as exc:
            telemetry.status = "cancelled"
            self._transition_once(telemetry, "cancelled")
            telemetry.total_ms = (time.perf_counter() - total_started) * 1000
            telemetry.error_stage = current_stage
            telemetry.error_type = "TurnCancelledError"
            self._publish_telemetry(telemetry)
            raise TurnCancelledError() from exc
        except OrchestratorError as exc:
            telemetry.status = "failed"
            self._transition_once(telemetry, "failed")
            telemetry.total_ms = (time.perf_counter() - total_started) * 1000
            telemetry.error_stage = exc.stage
            telemetry.error_type = type(exc).__name__
            self._publish_telemetry(telemetry)
            raise
        except Exception as exc:
            telemetry.status = "failed"
            self._transition_once(telemetry, "failed")
            telemetry.total_ms = (time.perf_counter() - total_started) * 1000
            telemetry.error_stage = current_stage
            telemetry.error_type = type(exc).__name__
            self._publish_telemetry(telemetry)
            raise ProviderUnavailableError(str(exc), stage=current_stage) from exc
        finally:
            if self._active_generations.get(session_id) == generation_id:
                self._active_generations.pop(session_id, None)
                self._active_tasks.pop(session_id, None)

    def cancel(self, session_id: str) -> bool:
        task = self._active_tasks.get(session_id)
        if task is None or task.done():
            return False
        self._active_generations.pop(session_id, None)
        task.cancel()
        return True

    async def _synthesize_sentence(
        self, sentence: str, sequence: int, context: TurnContext
    ) -> List[AudioChunk]:
        request = SynthesisRequest(
            text=sentence,
            language="zh-CN",
            voice_id="baseline",
            sequence=sequence,
            context=context,
        )
        output = []
        iterator = self.tts.synthesize(request).__aiter__()
        while True:
            try:
                chunk = await self._next_event(
                    iterator, self.settings.tts_timeout_seconds, "tts"
                )
            except StopAsyncIteration:
                break
            self._ensure_current(context)
            output.append(chunk)
        return output

    async def _with_timeout(self, awaitable, seconds: float, stage: str):
        try:
            return await asyncio.wait_for(awaitable, seconds)
        except asyncio.TimeoutError as exc:
            raise StageTimeoutError("%s timed out" % stage, stage=stage) from exc

    async def _next_event(self, iterator: AsyncIterator, seconds: float, stage: str):
        try:
            return await asyncio.wait_for(iterator.__anext__(), seconds)
        except asyncio.TimeoutError as exc:
            raise StageTimeoutError("%s timed out" % stage, stage=stage) from exc

    def _ensure_current(self, context: TurnContext) -> None:
        if self._active_generations.get(context.session_id) != context.generation_id:
            raise StaleGenerationError()

    def _transition(self, telemetry: TurnTelemetry, state: str) -> None:
        telemetry.states.append(state)
        if self.state_sink is not None:
            self.state_sink(state)

    def _transition_once(self, telemetry: TurnTelemetry, state: str) -> None:
        if not telemetry.states or telemetry.states[-1] != state:
            telemetry.states.append(state)
            if self.state_sink is not None:
                self.state_sink(state)

    def set_state_sink(self, sink: Optional[StateSink]) -> None:
        self.state_sink = sink

    def _publish_telemetry(self, telemetry: TurnTelemetry) -> None:
        self.last_telemetry = telemetry
        if self.telemetry_sink is not None:
            self.telemetry_sink(telemetry)
