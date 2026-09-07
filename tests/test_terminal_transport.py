import asyncio
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

try:
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosedError, InvalidStatus
except ImportError:
    connect = None

from dolls_orchestrator.terminal_transport import (
    TERMINAL_PATH,
    TerminalTurnRequest,
    TerminalTurnResponse,
    serve_terminal,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "terminal_protocol_v0.json"
TOKEN = "synthetic-loopback-token"


def _json(value):
    return json.dumps(value, ensure_ascii=False)


@unittest.skipIf(connect is None, "install the terminal extra for WebSocket tests")
class TerminalWebSocketLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.client_messages = fixture["client"]
        self.requests = []
        self.sessions = iter("loopback-%d" % index for index in range(1, 20))

        async def respond(request):
            self.requests.append(request)
            return TerminalTurnResponse(
                transcript="你好",
                reply_text="你好呀！",
                emotion="happy",
                audio_frames=(b"opus-one", b"opus-two"),
            )

        self.server = await serve_terminal(
            respond,
            TOKEN,
            port=0,
            session_id_factory=lambda: next(self.sessions),
        )
        port = self.server.sockets[0].getsockname()[1]
        self.base_uri = "ws://127.0.0.1:%d" % port

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    def headers(self, token=TOKEN):
        return {
            "Authorization": "Bearer " + token,
            "Protocol-Version": "1",
            "Device-Id": "loopback-device",
            "Client-Id": "loopback-client",
        }

    def open_client(self, path=TERMINAL_PATH, headers=None):
        return connect(
            self.base_uri + path,
            additional_headers=headers or self.headers(),
            compression=None,
            proxy=None,
        )

    async def hello(self, websocket):
        await websocket.send(_json(self.client_messages["hello"]))
        response = json.loads(await websocket.recv())
        self.assertEqual("hello", response["type"])
        return response["session_id"]

    async def test_authenticated_half_duplex_exchange_preserves_frames(self):
        async with self.open_client() as websocket:
            session_id = await self.hello(websocket)
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))
            await websocket.send(b"uplink-one")
            await websocket.send(b"uplink-two")
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))

            frames = [await websocket.recv() for _ in range(7)]
            text = [json.loads(frame) for frame in frames if isinstance(frame, str)]
            binary = [frame for frame in frames if isinstance(frame, bytes)]
            self.assertEqual(
                ["stt", "llm", "tts", "tts", "tts"],
                [message["type"] for message in text],
            )
            self.assertEqual(
                ["start", "sentence_start", "stop"],
                [message["state"] for message in text if message["type"] == "tts"],
            )
            self.assertEqual([b"opus-one", b"opus-two"], binary)

        self.assertEqual(1, len(self.requests))
        request = self.requests[0]
        self.assertEqual((b"uplink-one", b"uplink-two"), request.audio_frames)
        self.assertEqual("loopback-device", request.identity.device_id)
        self.assertNotIn(TOKEN, repr(request))
        with self.assertRaises(FrozenInstanceError):
            request.generation = 99

    async def test_bad_path_and_token_are_rejected_without_echo(self):
        secret = "never-echo-this-secret"
        for path, headers, status in (
            ("/unknown", self.headers(), 404),
            (TERMINAL_PATH, self.headers(secret), 401),
        ):
            with self.subTest(path=path, status=status):
                with self.assertRaises(InvalidStatus) as raised:
                    async with self.open_client(path, headers):
                        pass
                self.assertEqual(status, raised.exception.response.status_code)
                self.assertNotIn(secret, str(raised.exception.response))

    async def test_out_of_order_control_closes_without_handler_call(self):
        async with self.open_client() as websocket:
            session_id = await self.hello(websocket)
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))
            with self.assertRaises(ConnectionClosedError) as raised:
                await websocket.recv()
            self.assertEqual(1002, raised.exception.rcvd.code)
        self.assertEqual([], self.requests)

    async def test_malformed_text_closes_without_handler_call(self):
        async with self.open_client() as websocket:
            await self.hello(websocket)
            await websocket.send("{")
            with self.assertRaises(ConnectionClosedError) as raised:
                await websocket.recv()
            self.assertEqual(1002, raised.exception.rcvd.code)
        self.assertEqual([], self.requests)

    async def test_aggregate_audio_limit_closes_and_clears_turn(self):
        self.server.close()
        await self.server.wait_closed()

        async def respond(request):
            self.requests.append(request)
            raise AssertionError("oversized turn must not run")

        self.server = await serve_terminal(
            respond,
            TOKEN,
            port=0,
            max_turn_audio_bytes=5,
            session_id_factory=lambda: next(self.sessions),
        )
        port = self.server.sockets[0].getsockname()[1]
        self.base_uri = "ws://127.0.0.1:%d" % port

        async with self.open_client() as websocket:
            session_id = await self.hello(websocket)
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))
            await websocket.send(b"abc")
            await websocket.send(b"def")
            with self.assertRaises(ConnectionClosedError) as raised:
                await websocket.recv()
            self.assertEqual(1002, raised.exception.rcvd.code)
        self.assertEqual([], self.requests)

    async def test_abort_cancels_handler_and_suppresses_stale_output(self):
        self.server.close()
        await self.server.wait_closed()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def blocked(request):
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        self.server = await serve_terminal(
            blocked,
            TOKEN,
            port=0,
            session_id_factory=lambda: next(self.sessions),
        )
        port = self.server.sockets[0].getsockname()[1]
        self.base_uri = "ws://127.0.0.1:%d" % port

        async with self.open_client() as websocket:
            session_id = await self.hello(websocket)
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))
            await websocket.send(b"audio")
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))
            await asyncio.wait_for(started.wait(), 1)
            await websocket.send(_json({
                "type": "abort",
                "session_id": session_id,
                "reason": "user_cancelled",
            }))
            await asyncio.wait_for(cancelled.wait(), 1)
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(websocket.recv(), 0.05)
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))

    async def test_disconnect_cancels_response_work(self):
        self.server.close()
        await self.server.wait_closed()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def blocked(request):
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        self.server = await serve_terminal(
            blocked,
            TOKEN,
            port=0,
            session_id_factory=lambda: next(self.sessions),
        )
        port = self.server.sockets[0].getsockname()[1]
        self.base_uri = "ws://127.0.0.1:%d" % port

        async with self.open_client() as websocket:
            session_id = await self.hello(websocket)
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "start",
                "mode": "manual",
            }))
            await websocket.send(_json({
                "type": "listen",
                "session_id": session_id,
                "state": "stop",
            }))
            await asyncio.wait_for(started.wait(), 1)
            await websocket.close()
        await asyncio.wait_for(cancelled.wait(), 1)

    async def test_reconnect_uses_isolated_session_identity(self):
        async with self.open_client() as first:
            first_session = await self.hello(first)
        async with self.open_client() as second:
            second_session = await self.hello(second)
            self.assertNotEqual(first_session, second_session)
            await second.send(_json({
                "type": "listen",
                "session_id": first_session,
                "state": "start",
                "mode": "manual",
            }))
            with self.assertRaises(ConnectionClosedError) as raised:
                await second.recv()
            self.assertEqual(1002, raised.exception.rcvd.code)


if __name__ == "__main__":
    unittest.main()
