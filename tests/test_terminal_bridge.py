import asyncio
import json
from pathlib import Path
import unittest

try:
    from websockets.asyncio.client import connect
except ImportError:
    connect = None

from dolls_orchestrator.adapters.offline import (
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from dolls_orchestrator.config import Settings
from dolls_orchestrator.domain import AudioFormat
from dolls_orchestrator.errors import (
    ProviderUnavailableError,
    TerminalAudioBridgeError,
)
from dolls_orchestrator.orchestrator import TurnOrchestrator
from dolls_orchestrator.terminal_bridge import (
    DEFAULT_TERMINAL_EMOTION,
    UPLINK_PCM,
    DecodedTerminalAudio,
    OrchestratorTerminalBridge,
)
from dolls_orchestrator.terminal_protocol import (
    DOWNLINK_AUDIO,
    UPLINK_AUDIO,
    HandshakeIdentity,
)
from dolls_orchestrator.terminal_transport import (
    TERMINAL_PATH,
    TerminalTurnRequest,
    serve_terminal,
)


TOKEN = "synthetic-bridge-token"
_DEFAULT = object()


class SyntheticCodec:
    def __init__(self, decoded=_DEFAULT, encoded=_DEFAULT):
        self.decoded = (
            DecodedTerminalAudio(
                pcm=b"\0\0" * 1600,
                audio_format=UPLINK_PCM,
            )
            if decoded is _DEFAULT
            else decoded
        )
        self.encoded = (
            (b"synthetic-downlink-one", b"synthetic-downlink-two")
            if encoded is _DEFAULT
            else encoded
        )
        self.decode_calls = []
        self.encode_calls = []

    async def decode_uplink(self, frames, source):
        self.decode_calls.append((tuple(frames), source))
        await asyncio.sleep(0)
        return self.decoded

    async def encode_downlink(self, pcm, source, target):
        self.encode_calls.append((pcm, source, target))
        await asyncio.sleep(0)
        return self.encoded


class CapturingASR(OfflineASRAdapter):
    def __init__(self, transcript="桥接识别文本"):
        super().__init__(transcript)
        self.path = None
        self.existed_during_call = False

    async def transcribe(self, audio_path, context):
        self.path = Path(audio_path)
        self.existed_during_call = self.path.is_file()
        return await super().transcribe(audio_path, context)


class FailingASR(CapturingASR):
    async def transcribe(self, audio_path, context):
        self.path = Path(audio_path)
        self.existed_during_call = self.path.is_file()
        raise ProviderUnavailableError("synthetic failure", stage="asr")


class BlockingASR(CapturingASR):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()

    async def transcribe(self, audio_path, context):
        self.path = Path(audio_path)
        self.existed_during_call = self.path.is_file()
        self.started.set()
        await asyncio.Future()


def build_orchestrator(asr=None, reply="离线桥接回答。"):
    return TurnOrchestrator(
        asr or CapturingASR(),
        OfflineLLMAdapter(reply),
        ToneTTSAdapter(),
        Settings(),
    )


def request(frames=(b"synthetic-uplink-one", b"synthetic-uplink-two")):
    return TerminalTurnRequest(
        identity=HandshakeIdentity(1, "bridge-device", "bridge-client"),
        session_id="bridge-session",
        generation=1,
        audio_frames=frames,
    )


class TerminalBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_maps_exact_codec_boundaries_and_removes_wav(self):
        asr = CapturingASR()
        orchestrator = build_orchestrator(asr)
        codec = SyntheticCodec()
        response = await OrchestratorTerminalBridge(orchestrator, codec)(request())

        self.assertEqual("桥接识别文本", response.transcript)
        self.assertEqual("离线桥接回答。", response.reply_text)
        self.assertEqual(DEFAULT_TERMINAL_EMOTION, response.emotion)
        self.assertEqual(codec.encoded, response.audio_frames)
        self.assertEqual(
            ((b"synthetic-uplink-one", b"synthetic-uplink-two"), UPLINK_AUDIO),
            codec.decode_calls[0],
        )
        encoded_pcm, encoded_source, encoded_target = codec.encode_calls[0]
        self.assertTrue(encoded_pcm)
        self.assertEqual(AudioFormat(sample_rate=24000), encoded_source)
        self.assertEqual(DOWNLINK_AUDIO, encoded_target)
        self.assertTrue(asr.existed_during_call)
        self.assertFalse(asr.path.exists())
        self.assertEqual(1, orchestrator.conversations.turn_count("bridge-session"))

    async def test_empty_uplink_is_rejected_before_codec(self):
        codec = SyntheticCodec()
        bridge = OrchestratorTerminalBridge(build_orchestrator(), codec)
        with self.assertRaisesRegex(TerminalAudioBridgeError, "uplink audio is empty"):
            await bridge(request(frames=()))
        self.assertEqual([], codec.decode_calls)

    async def test_invalid_decoded_audio_is_rejected_before_orchestration(self):
        invalid_values = (
            DecodedTerminalAudio(b"", UPLINK_PCM),
            DecodedTerminalAudio(b"\0\0", AudioFormat(sample_rate=24000)),
            DecodedTerminalAudio(b"\0", UPLINK_PCM),
        )
        for decoded in invalid_values:
            with self.subTest(decoded=decoded):
                asr = CapturingASR()
                bridge = OrchestratorTerminalBridge(
                    build_orchestrator(asr), SyntheticCodec(decoded=decoded)
                )
                with self.assertRaises(TerminalAudioBridgeError):
                    await bridge(request())
                self.assertIsNone(asr.path)

    async def test_invalid_encoded_frames_fail_without_partial_response(self):
        for encoded in ((), (b"",), b"single-frame-not-a-sequence", None):
            with self.subTest(encoded=encoded):
                asr = CapturingASR()
                bridge = OrchestratorTerminalBridge(
                    build_orchestrator(asr), SyntheticCodec(encoded=encoded)
                )
                with self.assertRaises(TerminalAudioBridgeError):
                    await bridge(request())
                self.assertTrue(asr.existed_during_call)
                self.assertFalse(asr.path.exists())

    async def test_orchestrator_failure_preserves_type_and_cleans_wav(self):
        asr = FailingASR()
        bridge = OrchestratorTerminalBridge(build_orchestrator(asr), SyntheticCodec())
        with self.assertRaises(ProviderUnavailableError):
            await bridge(request())
        self.assertTrue(asr.existed_during_call)
        self.assertFalse(asr.path.exists())

    async def test_cancellation_returns_to_transport_and_cleans_wav(self):
        asr = BlockingASR()
        orchestrator = build_orchestrator(asr)
        bridge = OrchestratorTerminalBridge(orchestrator, SyntheticCodec())
        task = asyncio.create_task(bridge(request()))
        await asyncio.wait_for(asr.started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(asr.existed_during_call)
        self.assertFalse(asr.path.exists())
        self.assertEqual("cancelled", orchestrator.last_telemetry.status)
        self.assertEqual(0, orchestrator.conversations.turn_count("bridge-session"))


@unittest.skipIf(connect is None, "install the terminal extra for WebSocket tests")
class TerminalBridgeLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.codec = SyntheticCodec()
        self.orchestrator = build_orchestrator(
            CapturingASR("端到端识别"), reply="端到端回复。"
        )
        self.server = await serve_terminal(
            OrchestratorTerminalBridge(self.orchestrator, self.codec),
            TOKEN,
            port=0,
            session_id_factory=lambda: "integrated-session",
        )
        port = self.server.sockets[0].getsockname()[1]
        self.uri = "ws://127.0.0.1:%d%s" % (port, TERMINAL_PATH)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    def client(self):
        return connect(
            self.uri,
            additional_headers={
                "Authorization": "Bearer " + TOKEN,
                "Protocol-Version": "1",
                "Device-Id": "integrated-device",
                "Client-Id": "integrated-client",
            },
            compression=None,
            proxy=None,
        )

    async def begin_turn(self, websocket):
        await websocket.send(json.dumps({
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60,
            },
        }))
        hello = json.loads(await websocket.recv())
        session_id = hello["session_id"]
        await websocket.send(json.dumps({
            "type": "listen",
            "session_id": session_id,
            "state": "start",
            "mode": "manual",
        }))
        return session_id

    async def test_real_websocket_reaches_offline_orchestrator(self):
        async with self.client() as websocket:
            session_id = await self.begin_turn(websocket)
            await websocket.send(b"synthetic-uplink")
            await websocket.send(json.dumps({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))
            frames = [await websocket.recv() for _ in range(7)]

        messages = [json.loads(frame) for frame in frames if isinstance(frame, str)]
        audio = [frame for frame in frames if isinstance(frame, bytes)]
        self.assertEqual("端到端识别", messages[0]["text"])
        self.assertEqual("端到端回复。", messages[1]["text"])
        self.assertEqual("neutral", messages[1]["emotion"])
        self.assertEqual(
            ["start", "sentence_start", "stop"],
            [message["state"] for message in messages if message["type"] == "tts"],
        )
        self.assertEqual(list(self.codec.encoded), audio)
        self.assertEqual(1, self.orchestrator.conversations.turn_count(session_id))

    async def test_websocket_abort_cancels_bridge_without_failure_output(self):
        self.server.close()
        await self.server.wait_closed()
        asr = BlockingASR()
        cancelled = asyncio.Event()
        self.orchestrator = build_orchestrator(asr)

        def capture(telemetry):
            if telemetry.status == "cancelled":
                cancelled.set()

        self.orchestrator.telemetry_sink = capture
        self.server = await serve_terminal(
            OrchestratorTerminalBridge(self.orchestrator, SyntheticCodec()),
            TOKEN,
            port=0,
            session_id_factory=lambda: "abort-session",
        )
        port = self.server.sockets[0].getsockname()[1]
        self.uri = "ws://127.0.0.1:%d%s" % (port, TERMINAL_PATH)

        async with self.client() as websocket:
            session_id = await self.begin_turn(websocket)
            await websocket.send(b"synthetic-uplink")
            await websocket.send(json.dumps({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))
            await asyncio.wait_for(asr.started.wait(), 1)
            await websocket.send(json.dumps({
                "type": "abort",
                "session_id": session_id,
                "reason": "user_cancelled",
            }))
            await asyncio.wait_for(cancelled.wait(), 1)
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(websocket.recv(), 0.05)
            await websocket.send(json.dumps({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))

        self.assertFalse(asr.path.exists())
        self.assertEqual(0, self.orchestrator.conversations.turn_count(session_id))


if __name__ == "__main__":
    unittest.main()
