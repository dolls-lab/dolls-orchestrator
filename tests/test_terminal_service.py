import asyncio
from array import array
from contextlib import redirect_stdout
import io
import json
import math
import unittest
from unittest import mock

try:
    from websockets.asyncio.client import connect
except ImportError:
    connect = None

from dolls_orchestrator.cli import main
from dolls_orchestrator.config import Settings
from dolls_orchestrator.domain import AdapterHealth, AudioFormat
from dolls_orchestrator.errors import OpusCodecError, TerminalServiceError
from dolls_orchestrator.health import ServiceHealthReport
from dolls_orchestrator.opus_codec import LibOpusCodec, find_libopus
from dolls_orchestrator.terminal_protocol import DOWNLINK_AUDIO, UPLINK_AUDIO
from dolls_orchestrator.terminal_service import (
    TerminalServiceNotReadyError,
    run_terminal_service,
    start_terminal_service,
)
from dolls_orchestrator.terminal_transport import TERMINAL_PATH


TOKEN = "synthetic-runner-token"


def _native_library_available():
    try:
        find_libopus()
    except OpusCodecError:
        return False
    return True


NATIVE_LIBRARY_AVAILABLE = _native_library_available()


class FakeSocket:
    def getsockname(self):
        return ("127.0.0.1", 43210)


class FakeServer:
    def __init__(self):
        self.sockets = [FakeSocket()]
        self.close_calls = 0
        self.wait_closed_calls = 0

    def close(self):
        self.close_calls += 1

    async def wait_closed(self):
        self.wait_closed_calls += 1


def _ready_report():
    return ServiceHealthReport("offline", ())


class TerminalServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_assembles_handler_and_passes_secret_only_to_transport(self):
        server = FakeServer()
        captured = {}

        async def server_factory(handler, token, **kwargs):
            captured.update(handler=handler, token=token, kwargs=kwargs)
            return server

        with mock.patch(
            "dolls_orchestrator.terminal_service.check_service_health",
            return_value=_ready_report(),
        ), mock.patch("dolls_orchestrator.terminal_service.LibOpusCodec"):
            running = await start_terminal_service(
                Settings(terminal_token=TOKEN),
                port=0,
                server_factory=server_factory,
            )

        self.assertTrue(callable(captured["handler"]))
        self.assertEqual(TOKEN, captured["token"])
        self.assertEqual({"host": "127.0.0.1", "port": 0}, captured["kwargs"])
        self.assertEqual(43210, running.port)
        self.assertNotIn(TOKEN, json.dumps(running.status()))

    async def test_missing_token_blocks_before_server_factory(self):
        server_factory = mock.AsyncMock(side_effect=AssertionError("must not bind"))
        with self.assertRaises(TerminalServiceNotReadyError) as raised:
            await start_terminal_service(Settings(), server_factory=server_factory)
        self.assertEqual(
            "credential_missing", raised.exception.report.components[-1].reason
        )
        server_factory.assert_not_awaited()

    async def test_non_loopback_requires_explicit_opt_in(self):
        factory = mock.AsyncMock(side_effect=AssertionError("must not bind"))
        with self.assertRaisesRegex(TerminalServiceError, "explicit opt-in"):
            await start_terminal_service(
                Settings(terminal_token=TOKEN),
                host="0.0.0.0",
                server_factory=factory,
            )
        factory.assert_not_awaited()

        with mock.patch(
            "dolls_orchestrator.terminal_service.check_service_health",
            return_value=_ready_report(),
        ), mock.patch("dolls_orchestrator.terminal_service.LibOpusCodec"):
            await start_terminal_service(
                Settings(terminal_token=TOKEN),
                host="0.0.0.0",
                allow_lan=True,
                server_factory=mock.AsyncMock(return_value=FakeServer()),
            )

    async def test_shutdown_event_closes_and_awaits_server_once(self):
        server = FakeServer()
        shutdown = asyncio.Event()
        shutdown.set()
        with mock.patch(
            "dolls_orchestrator.terminal_service.check_service_health",
            return_value=_ready_report(),
        ), mock.patch("dolls_orchestrator.terminal_service.LibOpusCodec"):
            await run_terminal_service(
                Settings(terminal_token=TOKEN),
                shutdown_event=shutdown,
                server_factory=mock.AsyncMock(return_value=server),
            )
        self.assertEqual(1, server.close_calls)
        self.assertEqual(1, server.wait_closed_calls)

    async def test_cancellation_closes_server_before_propagating(self):
        server = FakeServer()
        started = asyncio.Event()
        with mock.patch(
            "dolls_orchestrator.terminal_service.check_service_health",
            return_value=_ready_report(),
        ), mock.patch("dolls_orchestrator.terminal_service.LibOpusCodec"):
            task = asyncio.create_task(run_terminal_service(
                Settings(terminal_token=TOKEN),
                shutdown_event=asyncio.Event(),
                on_started=lambda running: started.set(),
                server_factory=mock.AsyncMock(return_value=server),
            ))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(1, server.close_calls)
        self.assertEqual(1, server.wait_closed_calls)


class TerminalServiceCliTests(unittest.TestCase):
    def test_cli_has_no_token_argument_and_emits_secret_safe_status(self):
        async def run_service(settings, **kwargs):
            self.assertEqual(TOKEN, settings.terminal_token)
            running = mock.Mock()
            running.status.return_value = {
                "status": "listening",
                "profile": "offline",
                "host": "127.0.0.1",
                "port": 8765,
            }
            kwargs["on_started"](running)

        stdout = io.StringIO()
        with mock.patch.dict(
            "os.environ", {"DOLLS_TERMINAL_TOKEN": TOKEN}, clear=True
        ), mock.patch(
            "dolls_orchestrator.cli.run_terminal_service", side_effect=run_service
        ), redirect_stdout(stdout):
            self.assertEqual(0, main(["serve-terminal", "--profile", "offline"]))
        self.assertEqual("listening", json.loads(stdout.getvalue())["status"])
        self.assertNotIn(TOKEN, stdout.getvalue())

    def test_cli_blocked_readiness_returns_one_with_bounded_report(self):
        report = ServiceHealthReport(
            "offline",
            (
                AdapterHealth(
                    "terminal_auth",
                    "bearer-token",
                    "unknown",
                    "blocked",
                    "credential_missing",
                ),
            ),
        )

        async def blocked(*args, **kwargs):
            raise TerminalServiceNotReadyError(report)

        stdout = io.StringIO()
        with mock.patch.dict(
            "os.environ", {"DOLLS_TERMINAL_TOKEN": TOKEN}, clear=True
        ), mock.patch(
            "dolls_orchestrator.cli.run_terminal_service", side_effect=blocked
        ), redirect_stdout(stdout):
            self.assertEqual(1, main(["serve-terminal"]))
        self.assertEqual("blocked", json.loads(stdout.getvalue())["status"])
        self.assertNotIn(TOKEN, stdout.getvalue())


def _tone(sample_rate, duration_ms):
    samples = array(
        "h",
        (
            int(10000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            for index in range(sample_rate * duration_ms // 1000)
        ),
    )
    return samples.tobytes()


@unittest.skipUnless(
    NATIVE_LIBRARY_AVAILABLE and connect is not None,
    "system libopus and terminal extra are required",
)
class TerminalServiceLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_assembled_service_completes_real_opus_turn(self):
        settings = Settings(
            terminal_token=TOKEN,
            offline_transcript="runner 识别",
            offline_reply="runner 回复。",
        )
        running = await start_terminal_service(settings, port=0)
        codec = LibOpusCodec()
        uplink = await codec.encode_downlink(
            _tone(16000, 120), AudioFormat(sample_rate=16000), UPLINK_AUDIO
        )
        messages = []
        downlink = []
        try:
            uri = "ws://127.0.0.1:%d%s" % (running.port, TERMINAL_PATH)
            async with connect(
                uri,
                additional_headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Protocol-Version": "1",
                    "Device-Id": "runner-device",
                    "Client-Id": "runner-client",
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
                    messages.append(message)
                    if message.get("type") == "tts" and message.get("state") == "stop":
                        break
        finally:
            await running.close()

        decoded = await codec.decode_uplink(tuple(downlink), DOWNLINK_AUDIO)
        self.assertEqual("runner 识别", messages[0]["text"])
        self.assertEqual("runner 回复。", messages[1]["text"])
        self.assertTrue(decoded.pcm)


if __name__ == "__main__":
    unittest.main()
