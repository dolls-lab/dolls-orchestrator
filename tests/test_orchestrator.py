import asyncio
from pathlib import Path
import tempfile
import unittest

from dolls_orchestrator.adapters.offline import (
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from dolls_orchestrator.config import Settings
from dolls_orchestrator.domain import ASRResult
from dolls_orchestrator.errors import ProviderUnavailableError, StageTimeoutError, TurnCancelledError
from dolls_orchestrator.orchestrator import TurnOrchestrator

from tests.helpers import write_silent_wav


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


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
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

