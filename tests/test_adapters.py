import asyncio
from pathlib import Path
import tempfile
import unittest
import wave

from dolls_orchestrator.adapters.deepseek import DeepSeekPlaceholderAdapter
from dolls_orchestrator.adapters.macos_tts import MacOSSayTTSAdapter
from dolls_orchestrator.adapters.mlx_whisper import MLXWhisperAdapter
from dolls_orchestrator.adapters.offline import (
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from dolls_orchestrator.domain import SynthesisRequest, TurnContext
from dolls_orchestrator.errors import ProviderConfigurationError, ProviderUnavailableError

from tests.helpers import write_silent_wav


CONTEXT = TurnContext("session", "turn", "generation")


class AdapterContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_adapters_follow_normalized_contracts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            write_silent_wav(input_path)
            asr_result = await OfflineASRAdapter("测试").transcribe(input_path, CONTEXT)
            self.assertEqual("测试", asr_result.text)
            events = [
                event
                async for event in OfflineLLMAdapter("你好！", chunk_chars=1).stream_reply(
                    [{"role": "user", "content": "测试"}], CONTEXT
                )
            ]
            self.assertEqual("completed", events[-1].kind)
            request = SynthesisRequest("你好！", "zh-CN", "test", 0, CONTEXT)
            chunks = [chunk async for chunk in ToneTTSAdapter().synthesize(request)]
            self.assertTrue(chunks[0].data)
            self.assertEqual("pcm_s16le", chunks[0].audio_format.encoding)

    async def test_deepseek_placeholder_never_sends_network_request(self):
        adapter = DeepSeekPlaceholderAdapter(
            api_key=None,
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            network_enabled=False,
            max_output_tokens=256,
        )
        iterator = adapter.stream_reply([], CONTEXT).__aiter__()
        with self.assertRaisesRegex(ProviderConfigurationError, "disabled"):
            await iterator.__anext__()

    async def test_mlx_adapter_supports_injected_runner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            write_silent_wav(input_path, duration_ms=250)
            adapter = MLXWhisperAdapter(
                "test-model", runner=lambda path, model: {"text": "本地识别", "language": "zh"}
            )
            result = await adapter.transcribe(input_path, CONTEXT)
            self.assertEqual("本地识别", result.text)
            self.assertEqual(250, result.duration_ms)
            self.assertEqual("test-model", result.model)

    async def test_macos_adapter_normalizes_runner_output(self):
        commands = []

        async def fake_runner(command):
            commands.append(command)
            if command[0] == "say":
                output_path = Path(command[command.index("-o") + 1])
                output_path.write_bytes(b"aiff-placeholder")
            else:
                output_path = Path(command[-1])
                with wave.open(str(output_path), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)
                    wav_file.writeframes(b"\0\0" * 100)

        request = SynthesisRequest("你好", "zh-CN", "test", 0, CONTEXT)
        adapter = MacOSSayTTSAdapter(command_runner=fake_runner)
        chunks = [chunk async for chunk in adapter.synthesize(request)]
        self.assertEqual(["say", "afconvert"], [command[0] for command in commands])
        self.assertEqual(24000, chunks[0].audio_format.sample_rate)
        self.assertEqual(200, len(chunks[0].data))

    async def test_macos_adapter_rejects_empty_audio(self):
        async def fake_runner(command):
            output_path = Path(command[command.index("-o") + 1]) if command[0] == "say" else Path(command[-1])
            if command[0] == "say":
                output_path.write_bytes(b"aiff-placeholder")
            else:
                with wave.open(str(output_path), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)

        request = SynthesisRequest("你好", "zh-CN", "test", 0, CONTEXT)
        adapter = MacOSSayTTSAdapter(command_runner=fake_runner)
        with self.assertRaisesRegex(ProviderUnavailableError, "empty audio"):
            async for _ in adapter.synthesize(request):
                pass


if __name__ == "__main__":
    unittest.main()
