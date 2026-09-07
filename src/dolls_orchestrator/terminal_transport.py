"""Authenticated WebSocket transport for terminal protocol draft v0."""

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from typing import Awaitable, Callable, Optional, Tuple
import uuid

from .errors import TerminalProtocolError, TerminalStateError
from .terminal_protocol import (
    MAX_BINARY_FRAME_BYTES,
    ClientControl,
    ClientHello,
    HandshakeIdentity,
    TerminalSession,
    parse_client_text,
    serialize_server_message,
    server_llm,
    server_stt,
    server_tts,
    validate_binary_frame,
    validate_handshake_headers,
)


TERMINAL_PATH = "/xiaozhi/v1/"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_TURN_AUDIO_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class TerminalTurnRequest:
    identity: HandshakeIdentity
    session_id: str
    generation: int
    audio_frames: Tuple[bytes, ...]


@dataclass(frozen=True)
class TerminalTurnResponse:
    transcript: str
    reply_text: str
    emotion: str
    audio_frames: Tuple[bytes, ...]


TerminalTurnHandler = Callable[[TerminalTurnRequest], Awaitable[TerminalTurnResponse]]


class TerminalWebSocketConnection:
    """Own one accepted WebSocket connection and its response task."""

    def __init__(
        self,
        websocket,
        identity: HandshakeIdentity,
        turn_handler: TerminalTurnHandler,
        session_id: str,
        max_turn_audio_bytes: int = MAX_TURN_AUDIO_BYTES,
    ) -> None:
        if max_turn_audio_bytes <= 0:
            raise ValueError("max_turn_audio_bytes must be greater than zero")
        self._websocket = websocket
        self._identity = identity
        self._turn_handler = turn_handler
        self._session = TerminalSession(session_id)
        self._max_turn_audio_bytes = max_turn_audio_bytes
        self._audio_frames = []
        self._audio_bytes = 0
        self._response_task: Optional[asyncio.Task] = None

    @property
    def session(self) -> TerminalSession:
        return self._session

    async def run(self) -> None:
        try:
            async for frame in self._websocket:
                await self._receive(frame)
        except (TerminalProtocolError, TerminalStateError):
            await self._websocket.close(code=1002, reason="terminal protocol error")
        finally:
            self._session.disconnect()
            await self._cancel_response()
            self._clear_audio()

    async def _receive(self, frame) -> None:
        if isinstance(frame, str):
            await self._receive_text(frame)
            return
        if isinstance(frame, bytes):
            self._receive_audio(frame)
            return
        raise TerminalProtocolError("unsupported WebSocket frame type")

    async def _receive_text(self, frame: str) -> None:
        message = parse_client_text(frame)
        if isinstance(message, ClientHello):
            hello = self._session.accept_hello(message)
            await self._websocket.send(serialize_server_message(hello))
            return

        if not isinstance(message, ClientControl):
            raise TerminalProtocolError("unsupported terminal message")

        generation = self._session.accept_control(message)
        if message.message_type == "listen" and message.state == "start":
            self._clear_audio()
            return
        if message.message_type == "listen" and message.state == "stop":
            request = TerminalTurnRequest(
                identity=self._identity,
                session_id=self._session.session_id,
                generation=generation,
                audio_frames=tuple(self._audio_frames),
            )
            self._clear_audio()
            self._response_task = asyncio.create_task(self._deliver_response(request))
            return
        if message.message_type in {"abort", "goodbye"}:
            self._clear_audio()
            await self._cancel_response()
            if message.message_type == "goodbye":
                await self._websocket.close(code=1000, reason="terminal goodbye")

    def _receive_audio(self, frame: bytes) -> None:
        accepted = self._session.accept_uplink_audio(frame)
        if accepted is None:
            return
        next_size = self._audio_bytes + len(accepted)
        if next_size > self._max_turn_audio_bytes:
            self._clear_audio()
            raise TerminalProtocolError("terminal turn audio is too large")
        self._audio_frames.append(accepted)
        self._audio_bytes = next_size

    async def _deliver_response(self, request: TerminalTurnRequest) -> None:
        try:
            response = await self._turn_handler(request)
            if not isinstance(response, TerminalTurnResponse):
                raise TerminalProtocolError("terminal turn handler returned invalid response")

            messages = (
                server_stt(request.session_id, response.transcript),
                server_llm(request.session_id, response.emotion, response.reply_text),
                server_tts(request.session_id, "start"),
                server_tts(request.session_id, "sentence_start", response.reply_text),
            )
            audio_frames = tuple(validate_binary_frame(frame) for frame in response.audio_frames)
            if not audio_frames:
                raise TerminalProtocolError("terminal response audio must not be empty")

            if not self._session.is_current_generation(request.generation):
                return
            self._session.begin_speaking(request.generation)
            for message in messages:
                if not await self._send_current(
                    request.generation, serialize_server_message(message)
                ):
                    return
            for frame in audio_frames:
                released = self._session.release_downlink_audio(
                    request.generation, frame
                )
                if released is None:
                    return
                await self._websocket.send(released)
            if not await self._send_current(
                request.generation,
                serialize_server_message(server_tts(request.session_id, "stop")),
            ):
                return
            self._session.complete_speaking(request.generation)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._websocket.close(code=1011, reason="terminal turn failed")

    async def _send_current(self, generation: int, payload: str) -> bool:
        if not self._session.is_current_generation(generation):
            return False
        await self._websocket.send(payload)
        return True

    async def _cancel_response(self) -> None:
        task = self._response_task
        self._response_task = None
        if task is None or task.done():
            if task is not None and not task.cancelled():
                task.exception()
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _clear_audio(self) -> None:
        self._audio_frames.clear()
        self._audio_bytes = 0


async def serve_terminal(
    turn_handler: TerminalTurnHandler,
    expected_token: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    path: str = TERMINAL_PATH,
    max_turn_audio_bytes: int = MAX_TURN_AUDIO_BYTES,
    session_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
):
    """Create and start a WebSocket server; the caller owns server shutdown."""

    if not expected_token or any(character.isspace() for character in expected_token):
        raise ValueError("expected_token must be a non-empty token")
    if not path.startswith("/"):
        raise ValueError("terminal path must start with /")

    try:
        from websockets.asyncio.server import serve
    except ImportError as exc:
        raise RuntimeError(
            "terminal transport requires the 'terminal' package extra"
        ) from exc

    def process_request(connection, request):
        if request.path != path:
            return connection.respond(HTTPStatus.NOT_FOUND, "not found\n")
        try:
            validate_handshake_headers(request.headers, expected_token)
        except TerminalProtocolError:
            return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
        return None

    async def connection_handler(websocket):
        try:
            identity = validate_handshake_headers(
                websocket.request.headers, expected_token
            )
        except TerminalProtocolError:
            await websocket.close(code=1008, reason="terminal authorization failed")
            return
        connection = TerminalWebSocketConnection(
            websocket=websocket,
            identity=identity,
            turn_handler=turn_handler,
            session_id=session_id_factory(),
            max_turn_audio_bytes=max_turn_audio_bytes,
        )
        await connection.run()

    return await serve(
        connection_handler,
        host,
        port,
        process_request=process_request,
        compression=None,
        max_size=MAX_BINARY_FRAME_BYTES,
        server_header=None,
    )
