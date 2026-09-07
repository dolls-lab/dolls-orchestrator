import asyncio
from pathlib import Path
import tempfile
import unittest

from dolls_orchestrator.character import load_character_package
from dolls_orchestrator.adapters.offline import (
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from dolls_orchestrator.config import Settings
from dolls_orchestrator.domain import ASRResult, LLMEvent
from dolls_orchestrator.errors import ProviderUnavailableError, StageTimeoutError, TurnCancelledError
from dolls_orchestrator.orchestrator import TurnOrchestrator

from tests.helpers import write_character_package, write_silent_wav


class SlowASR:
    async def transcribe(self, audio_path, context):
        await asyncio.sleep(1)


class FailOnceASR:
    def __init__(self):
        self.calls = 0

    async def transcribe(self, audio_path, context):
        self.calls += 1
        if self.calls == 1:
            raise ProviderUnavailableError("temporary failure", stage="asr")
        return await OfflineASRAdapter("恢复成功").transcribe(audio_path, context)


class CapturingLLM:
    def __init__(self):
        self.calls = []

    async def stream_reply(self, messages, context):
        self.calls.append(list(messages))
        yield LLMEvent(kind="text_delta", text="角色回答。")
        yield LLMEvent(
            kind="completed",
            provider="capture",
            model="capture-v1",
            usage={"input_messages": len(messages)},
            elapsed_ms=0.1,
        )


class AlwaysFailASR:
    async def transcribe(self, audio_path, context):
        raise ProviderUnavailableError("failed", stage="asr")


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_character_examples_precede_bounded_runtime_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "input.wav"
            write_silent_wav(path)
            character = load_character_package(
                write_character_package(root / "character")
            )
            llm = CapturingLLM()
            orchestrator = TurnOrchestrator(
                OfflineASRAdapter("当前问题"),
                llm,
                ToneTTSAdapter(),
                Settings(context_turns=1),
                character=character,
            )
            orchestrator.conversations.commit("character-session", "历史问题", "历史回答")
            result = await orchestrator.run_turn(path, "character-session")
            self.assertEqual(
                ["system", "user", "assistant", "user", "assistant", "user"],
                [message["role"] for message in llm.calls[0]],
            )
            self.assertEqual("你是测试三月七。", llm.calls[0][0]["content"])
            self.assertEqual("示例问题", llm.calls[0][1]["content"])
            self.assertEqual("历史问题", llm.calls[0][3]["content"])
            self.assertEqual("当前问题", llm.calls[0][-1]["content"])
            self.assertEqual("march-7th", result.telemetry.character_id)
            self.assertEqual("0.1.0", result.telemetry.character_version)
            telemetry = result.telemetry.to_dict()
            self.assertNotIn("system_prompt", telemetry)
            self.assertNotIn("character-session", str(telemetry.get("character_version")))

    async def test_failure_telemetry_contains_only_character_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "input.wav"
            write_silent_wav(path)
            character = load_character_package(
                write_character_package(root / "character")
            )
            orchestrator = TurnOrchestrator(
                AlwaysFailASR(),
                OfflineLLMAdapter("unused"),
                ToneTTSAdapter(),
                Settings(),
                character=character,
            )
            with self.assertRaises(ProviderUnavailableError):
                await orchestrator.run_turn(path)
            telemetry = orchestrator.last_telemetry.to_dict()
            self.assertEqual("march-7th", telemetry["character_id"])
            self.assertEqual("0.1.0", telemetry["character_version"])
            self.assertNotIn("你是测试", str(telemetry))

    async def test_timeout_has_typed_telemetry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.wav"
            write_silent_wav(path)
            settings = Settings(asr_timeout_seconds=0.01)
            orchestrator = TurnOrchestrator(
                SlowASR(), OfflineLLMAdapter("不会运行"), ToneTTSAdapter(), settings
            )
            with self.assertRaises(StageTimeoutError):
                await orchestrator.run_turn(path)
            self.assertEqual("failed", orchestrator.last_telemetry.status)
            self.assertEqual("asr", orchestrator.last_telemetry.error_stage)

    async def test_failure_does_not_poison_next_turn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.wav"
            write_silent_wav(path)
            asr = FailOnceASR()
            orchestrator = TurnOrchestrator(
                asr, OfflineLLMAdapter("第二轮成功。"), ToneTTSAdapter(), Settings()
            )
            with self.assertRaises(ProviderUnavailableError):
                await orchestrator.run_turn(path)
            result = await orchestrator.run_turn(path)
            self.assertEqual("completed", result.telemetry.status)
            self.assertEqual(1, orchestrator.conversations.turn_count("desktop"))

    async def test_new_generation_cancels_old_turn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.wav"
            write_silent_wav(path)
            orchestrator = TurnOrchestrator(
                OfflineASRAdapter("问题"),
                OfflineLLMAdapter("这是一个会被分块生成的回答。", chunk_chars=1, delay_seconds=0.03),
                ToneTTSAdapter(),
                Settings(),
            )
            first = asyncio.create_task(orchestrator.run_turn(path, "same-session"))
            await asyncio.sleep(0.05)
            second = asyncio.create_task(orchestrator.run_turn(path, "same-session"))
            with self.assertRaises(TurnCancelledError):
                await first
            result = await second
            self.assertEqual("completed", result.telemetry.status)
            self.assertEqual(1, orchestrator.conversations.turn_count("same-session"))

    async def test_explicit_cancel_stops_turn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.wav"
            write_silent_wav(path)
            orchestrator = TurnOrchestrator(
                OfflineASRAdapter("问题"),
                OfflineLLMAdapter("缓慢回答。", chunk_chars=1, delay_seconds=0.1),
                ToneTTSAdapter(),
                Settings(),
            )
            task = asyncio.create_task(orchestrator.run_turn(path, "cancel-session"))
            await asyncio.sleep(0.03)
            self.assertTrue(orchestrator.cancel("cancel-session"))
            with self.assertRaises(TurnCancelledError):
                await task
            self.assertEqual(0, orchestrator.conversations.turn_count("cancel-session"))


if __name__ == "__main__":
    unittest.main()
