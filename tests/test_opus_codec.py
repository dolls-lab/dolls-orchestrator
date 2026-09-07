import asyncio
from array import array
import json
import math
from pathlib import Path
import tempfile
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
from dolls_orchestrator.errors import OpusCodecError
from dolls_orchestrator.opus_codec import LibOpusCodec, find_libopus
from dolls_orchestrator.orchestrator import TurnOrchestrator
from dolls_orchestrator.terminal_bridge import OrchestratorTerminalBridge
from dolls_orchestrator.terminal_protocol import (
    AudioParameters,
    DOWNLINK_AUDIO,
    UPLINK_AUDIO,
)
from dolls_orchestrator.terminal_transport import TERMINAL_PATH, serve_terminal


TOKEN = "synthetic-native-codec-token"


def _native_library_available():
    try:
        find_libopus()
    except OpusCodecError:
        return False
    return True


NATIVE_LIBRARY_AVAILABLE = _native_library_available()


def _tone(sample_rate, duration_ms, frequency=440, amplitude=10000):
    sample_count = sample_rate * duration_ms // 1000
    samples = array(
        "h",
        (
            int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            for index in range(sample_count)
        ),
    )
    return samples.tobytes()


def _energy(pcm):
    samples = array("h")
    samples.frombytes(pcm)
    return sum(abs(sample) for sample in samples) / max(1, len(samples))


@unittest.skipUnless(NATIVE_LIBRARY_AVAILABLE, "system libopus is unavailable")
class NativeOpusCodecTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.codec = LibOpusCodec()

    def test_discovery_reports_native_version(self):
        self.assertTrue(self.codec.library_path)
        self.assertRegex(self.codec.version, r"^libopus \d+")

    async def test_16khz_packets_round_trip_in_order(self):
        pcm = _tone(16000, 180)
        packets = await self.codec.encode_downlink(
            pcm, AudioFormat(sample_rate=16000), UPLINK_AUDIO
        )
        decoded = await self.codec.decode_uplink(packets, UPLINK_AUDIO)

        self.assertEqual(3, len(packets))
        self.assertTrue(all(0 < len(packet) <= 4000 for packet in packets))
        self.assertEqual(AudioFormat(sample_rate=16000), decoded.audio_format)
        self.assertEqual(len(pcm), len(decoded.pcm))
        self.assertGreater(_energy(decoded.pcm), 500)

    async def test_24khz_encoding_pads_only_final_frame(self):
        pcm = _tone(24000, 75)
        packets = await self.codec.encode_downlink(
            pcm, AudioFormat(sample_rate=24000), DOWNLINK_AUDIO
        )
        decoded = await self.codec.decode_uplink(packets, DOWNLINK_AUDIO)

        self.assertEqual(2, len(packets))
        self.assertEqual(2 * 1440 * 2, len(decoded.pcm))
        self.assertGreater(_energy(decoded.pcm), 300)

    async def test_resamples_16khz_pcm_for_24khz_downlink(self):
        pcm = _tone(16000, 120)
        packets = await self.codec.encode_downlink(
            pcm, AudioFormat(sample_rate=16000), DOWNLINK_AUDIO
        )
        decoded = await self.codec.decode_uplink(packets, DOWNLINK_AUDIO)

        self.assertEqual(2, len(packets))
        self.assertEqual(24000 * 120 // 1000 * 2, len(decoded.pcm))
        self.assertGreater(_energy(decoded.pcm), 300)

    async def test_invalid_inputs_are_normalized(self):
        invalid_target = AudioParameters("opus", 24000, 2, 60)
        cases = (
            self.codec.decode_uplink((), UPLINK_AUDIO),
            self.codec.decode_uplink((b"\xff",), UPLINK_AUDIO),
            self.codec.encode_downlink(
                b"\x00", AudioFormat(sample_rate=24000), DOWNLINK_AUDIO
            ),
            self.codec.encode_downlink(
                b"\x00\x00", AudioFormat(sample_rate=24000), invalid_target
            ),
        )
        for operation in cases:
            with self.subTest(operation=operation):
                with self.assertRaises(OpusCodecError) as raised:
                    await operation
                self.assertEqual("terminal_audio_codec", raised.exception.stage)


class NativeOpusDiscoveryTests(unittest.TestCase):
    def test_missing_explicit_library_uses_static_error(self):
        missing = Path(tempfile.gettempdir()) / "dolls-libopus-does-not-exist.dylib"
        with self.assertRaisesRegex(
            OpusCodecError, "native libopus is unavailable"
        ) as raised:
            LibOpusCodec(str(missing))
        self.assertEqual("terminal_audio_codec", raised.exception.stage)
        self.assertNotIn(str(missing), str(raised.exception))


@unittest.skipUnless(
    NATIVE_LIBRARY_AVAILABLE and connect is not None,
    "system libopus and terminal extra are required",
)
class NativeOpusLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.codec = LibOpusCodec()
        orchestrator = TurnOrchestrator(
            OfflineASRAdapter("真实编解码识别"),
            OfflineLLMAdapter("真实编解码回复。"),
            ToneTTSAdapter(),
            Settings(),
        )
        self.server = await serve_terminal(
            OrchestratorTerminalBridge(orchestrator, self.codec),
            TOKEN,
            port=0,
            session_id_factory=lambda: "native-opus-session",
        )
        port = self.server.sockets[0].getsockname()[1]
        self.uri = "ws://127.0.0.1:%d%s" % (port, TERMINAL_PATH)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_real_opus_websocket_offline_orchestration(self):
        uplink = await self.codec.encode_downlink(
            _tone(16000, 120), AudioFormat(sample_rate=16000), UPLINK_AUDIO
        )
        text_messages = []
        downlink = []
        async with connect(
            self.uri,
            additional_headers={
                "Authorization": "Bearer " + TOKEN,
                "Protocol-Version": "1",
                "Device-Id": "native-opus-device",
                "Client-Id": "native-opus-client",
            },
            compression=None,
            proxy=None,
        ) as websocket:
            await websocket.send(json.dumps({
                "type": "hello",
                "version": 1,
                "transport": "websocket",
                "audio_params": UPLINK_AUDIO.to_dict(),
            }))
            hello = json.loads(await websocket.recv())
            session_id = hello["session_id"]
            await websocket.send(json.dumps({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))
            for packet in uplink:
                await websocket.send(packet)
            await websocket.send(json.dumps({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))

            while True:
                frame = await asyncio.wait_for(websocket.recv(), 2)
                if isinstance(frame, bytes):
                    downlink.append(frame)
                    continue
                message = json.loads(frame)
                text_messages.append(message)
                if message.get("type") == "tts" and message.get("state") == "stop":
                    break

        decoded = await self.codec.decode_uplink(tuple(downlink), DOWNLINK_AUDIO)
        self.assertEqual(
            ["stt", "llm", "tts", "tts", "tts"],
            [message["type"] for message in text_messages],
        )
        self.assertEqual("真实编解码识别", text_messages[0]["text"])
        self.assertEqual("真实编解码回复。", text_messages[1]["text"])
        self.assertTrue(downlink)
        self.assertGreater(_energy(decoded.pcm), 100)


if __name__ == "__main__":
    unittest.main()
