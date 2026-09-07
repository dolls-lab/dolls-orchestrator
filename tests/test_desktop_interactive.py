import asyncio
from pathlib import Path
import tempfile
import unittest
import wave

from dolls_orchestrator.adapters.offline import OfflineASRAdapter, OfflineLLMAdapter, ToneTTSAdapter
from dolls_orchestrator.config import Settings
from dolls_orchestrator.desktop_audio import AfplayPlayer, SoundDeviceRecorder
from dolls_orchestrator.errors import MicrophoneError
from dolls_orchestrator.interactive import InteractiveSession
from dolls_orchestrator.orchestrator import TurnOrchestrator

from tests.helpers import write_silent_wav


class FakeInputStream:
    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        self.started = True
        self.callback(b"\x01\x00" * 320, 320, None, None)

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeSoundDevice:
    def __init__(self):
        self.stream = None

    def RawInputStream(self, **kwargs):
        self.stream = FakeInputStream(**kwargs)
        return self.stream

    def query_devices(self):
        return [{"name": "Fake microphone", "max_input_channels": 1}]


class DesktopAudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_sounddevice_recorder_writes_expected_wav(self):
        module = FakeSoundDevice()
        recorder = SoundDeviceRecorder(sounddevice_module=module)
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "recorded.wav"
            await recorder.record_until(output, asyncio.sleep(0))
            with wave.open(str(output), "rb") as wav_file:
                self.assertEqual(16000, wav_file.getframerate())
                self.assertEqual(1, wav_file.getnchannels())
                self.assertEqual(320, wav_file.getnframes())
        self.assertTrue(module.stream.started)
        self.assertTrue(module.stream.stopped)
        self.assertTrue(module.stream.closed)

    async def test_empty_recording_is_rejected(self):
        class EmptyStream(FakeInputStream):
            def start(self):
                self.started = True

        class EmptyModule(FakeSoundDevice):
            def RawInputStream(self, **kwargs):
                self.stream = EmptyStream(**kwargs)
                return self.stream

        recorder = SoundDeviceRecorder(sounddevice_module=EmptyModule())
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(MicrophoneError, "no audio"):
                await recorder.record_until(Path(temp_dir) / "empty.wav", asyncio.sleep(0))

    async def test_device_listing_is_injectable(self):
        recorder = SoundDeviceRecorder(sounddevice_module=FakeSoundDevice())
        self.assertIn("Fake microphone", recorder.list_devices())

    async def test_afplay_success_and_cancellation_cleanup(self):
        class FakeProcess:
            def __init__(self, slow=False):
                self.returncode = 0
                self.slow = slow
                self.terminated = False

            async def communicate(self):
                if self.slow:
                    await asyncio.sleep(10)
                return b"", b""

            def terminate(self):
                self.terminated = True

            async def wait(self):
                self.returncode = -15

        processes = []

        async def factory(*args, **kwargs):
            process = FakeProcess(slow=len(processes) == 1)
            processes.append(process)
            return process

        player = AfplayPlayer(process_factory=factory)
        await player.play(Path("reply.wav"))
        task = asyncio.create_task(player.play(Path("reply.wav")))
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(processes[1].terminated)


class FakeRecorder:
    def __init__(self, fail_first=False):
        self.calls = 0
        self.paths = []
        self.fail_first = fail_first

    async def record_until(self, output_path, stop_signal):
        self.calls += 1
        await stop_signal
        if self.fail_first and self.calls == 1:
            raise MicrophoneError("simulated microphone failure")
        write_silent_wav(output_path)
        self.paths.append(output_path)


class FakePlayer:
    def __init__(self):
        self.paths = []

    async def play(self, audio_path):
        self.assertable_exists = audio_path.exists()
        self.paths.append(audio_path)


class ScriptedPrompt:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def __call__(self, text):
        return next(self.responses)


def offline_orchestrator():
    return TurnOrchestrator(
        OfflineASRAdapter("你好吗？"),
        OfflineLLMAdapter("我很好呀！"),
        ToneTTSAdapter(),
        Settings(),
    )


class InteractiveSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_turn_emits_states_and_cleans_temp_files(self):
        output = []
        recorder = FakeRecorder()
        player = FakePlayer()
        session = InteractiveSession(
            offline_orchestrator(),
            recorder,
            player,
            prompt=ScriptedPrompt(["", ""]),
            output=output.append,
        )
        completed = await session.run(max_turns=1)
        self.assertEqual(1, completed)
        self.assertTrue(player.assertable_exists)
        self.assertFalse(player.paths[0].exists())
        joined = "\n".join(output)
        for state in (
            "[idle]",
            "[listening]",
            "[transcribing]",
            "[generating]",
            "[synthesizing]",
            "[playing]",
            "[completed]",
        ):
            self.assertIn(state, joined)

    async def test_failure_returns_to_idle_and_retries(self):
        output = []
        recorder = FakeRecorder(fail_first=True)
        session = InteractiveSession(
            offline_orchestrator(),
            recorder,
            None,
            prompt=ScriptedPrompt(["", "", "", ""]),
            output=output.append,
        )
        completed = await session.run(max_turns=1)
        self.assertEqual(1, completed)
        self.assertEqual(2, recorder.calls)
        self.assertIn("[recoverable_error]", "\n".join(output))
        self.assertNotIn("[playing]", "\n".join(output))

    async def test_quit_does_not_record(self):
        recorder = FakeRecorder()
        session = InteractiveSession(
            offline_orchestrator(),
            recorder,
            None,
            prompt=ScriptedPrompt(["q"]),
            output=lambda message: None,
        )
        self.assertEqual(0, await session.run())
        self.assertEqual(0, recorder.calls)


if __name__ == "__main__":
    unittest.main()
