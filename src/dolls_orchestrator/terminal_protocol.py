"""Pure protocol draft v0 codec and connection-scoped terminal state."""

from dataclasses import dataclass
from enum import Enum
import hmac
import json
from typing import Any, Dict, Mapping, Optional

from .errors import TerminalProtocolError, TerminalStateError


DRAFT_VERSION = "0"
UPSTREAM_RELEASE = "v2.4.2"
UPSTREAM_COMMIT = "e8d8a40"
PROTOCOL_VERSION = 1
TRANSPORT = "websocket"
UPLINK_SAMPLE_RATE = 16000
DOWNLINK_SAMPLE_RATE = 24000
CHANNELS = 1
FRAME_DURATION_MS = 60
MAX_BINARY_FRAME_BYTES = 65536
LISTEN_MODES = {"manual", "auto", "realtime"}


@dataclass(frozen=True)
class HandshakeIdentity:
    protocol_version: int
    device_id: str
    client_id: str


@dataclass(frozen=True)
class AudioParameters:
    format: str
    sample_rate: int
    channels: int
    frame_duration: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "frame_duration": self.frame_duration,
        }


UPLINK_AUDIO = AudioParameters("opus", UPLINK_SAMPLE_RATE, CHANNELS, FRAME_DURATION_MS)
DOWNLINK_AUDIO = AudioParameters("opus", DOWNLINK_SAMPLE_RATE, CHANNELS, FRAME_DURATION_MS)


@dataclass(frozen=True)
class ClientHello:
    version: int
    transport: str
    audio: AudioParameters


@dataclass(frozen=True)
class ClientControl:
    message_type: str
    session_id: str
    state: Optional[str] = None
    mode: Optional[str] = None
    reason: Optional[str] = None


class TerminalState(str, Enum):
    AWAITING_HELLO = "awaiting_hello"
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    CLOSED = "closed"


def _static_error(message: str) -> TerminalProtocolError:
    return TerminalProtocolError(message)


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _static_error("terminal %s must be a non-empty string" % label)
    normalized = value.strip()
    if len(normalized) > 256:
        raise _static_error("terminal %s is too long" % label)
    return normalized


def validate_handshake_headers(
    headers: Mapping[str, str], expected_token: Optional[str] = None
) -> HandshakeIdentity:
    normalized = {str(key).lower(): str(value).strip() for key, value in headers.items()}
    if normalized.get("protocol-version") != str(PROTOCOL_VERSION):
        raise _static_error("unsupported terminal protocol version")
    device_id = _nonempty(normalized.get("device-id"), "device ID")
    client_id = _nonempty(normalized.get("client-id"), "client ID")
    authorization = normalized.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise _static_error("terminal authorization is invalid")
    supplied_token = authorization[7:]
    if not supplied_token or any(character.isspace() for character in supplied_token):
        raise _static_error("terminal authorization is invalid")
    if expected_token is not None:
        if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
            raise _static_error("terminal authorization is invalid")
    return HandshakeIdentity(
        protocol_version=PROTOCOL_VERSION,
        device_id=device_id,
        client_id=client_id,
    )


def _object_from_json(text: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise _static_error("invalid terminal JSON message") from exc
    if not isinstance(value, dict):
        raise _static_error("terminal JSON message must be an object")
    return value


def _exact_fields(value: Mapping[str, Any], allowed, required) -> None:
    keys = set(value)
    if not set(required).issubset(keys) or not keys.issubset(set(allowed)):
        raise _static_error("terminal message fields are invalid")


def _parse_audio(value: Any) -> AudioParameters:
    if not isinstance(value, dict):
        raise _static_error("terminal audio parameters must be an object")
    _exact_fields(
        value,
        {"format", "sample_rate", "channels", "frame_duration"},
        {"format", "sample_rate", "channels", "frame_duration"},
    )
    audio = AudioParameters(
        format=value.get("format"),
        sample_rate=value.get("sample_rate"),
        channels=value.get("channels"),
        frame_duration=value.get("frame_duration"),
    )
    if audio != UPLINK_AUDIO:
        raise _static_error("unsupported terminal uplink audio parameters")
    return audio


def parse_client_text(text: str):
    value = _object_from_json(text)
    message_type = value.get("type")
    if message_type == "hello":
        _exact_fields(
            value,
            {"type", "version", "transport", "audio_params", "features", "text_font"},
            {"type", "version", "transport", "audio_params"},
        )
        if value.get("version") != PROTOCOL_VERSION:
            raise _static_error("unsupported terminal hello version")
        if value.get("transport") != TRANSPORT:
            raise _static_error("unsupported terminal transport")
        for optional in ("features", "text_font"):
            if optional in value and not isinstance(value[optional], dict):
                raise _static_error("terminal optional hello fields must be objects")
        return ClientHello(
            version=PROTOCOL_VERSION,
            transport=TRANSPORT,
            audio=_parse_audio(value.get("audio_params")),
        )
    if message_type == "listen":
        _exact_fields(
            value,
            {"type", "session_id", "state", "mode"},
            {"type", "session_id", "state"},
        )
        session_id = _nonempty(value.get("session_id"), "session ID")
        state = value.get("state")
        if state not in {"start", "stop"}:
            raise _static_error("unsupported terminal listen state")
        mode = value.get("mode")
        if state == "start" and mode not in LISTEN_MODES:
            raise _static_error("unsupported terminal listen mode")
        if state == "stop" and mode is not None:
            raise _static_error("terminal listen stop must not include mode")
        return ClientControl("listen", session_id, state=state, mode=mode)
    if message_type == "abort":
        _exact_fields(
            value,
            {"type", "session_id", "reason"},
            {"type", "session_id"},
        )
        reason = value.get("reason")
        if reason is not None:
            reason = _nonempty(reason, "abort reason")
        return ClientControl(
            "abort", _nonempty(value.get("session_id"), "session ID"), reason=reason
        )
    if message_type == "goodbye":
        _exact_fields(value, {"type", "session_id"}, {"type", "session_id"})
        return ClientControl(
            "goodbye", _nonempty(value.get("session_id"), "session ID")
        )
    raise _static_error("unsupported terminal message type")


def server_hello(session_id: str) -> Dict[str, Any]:
    return {
        "type": "hello",
        "transport": TRANSPORT,
        "session_id": _nonempty(session_id, "session ID"),
        "audio_params": DOWNLINK_AUDIO.to_dict(),
    }


def server_stt(session_id: str, text: str) -> Dict[str, Any]:
    return {
        "session_id": _nonempty(session_id, "session ID"),
        "type": "stt",
        "text": _nonempty(text, "STT text"),
    }


def server_llm(session_id: str, emotion: str, text: str = "") -> Dict[str, Any]:
    return {
        "session_id": _nonempty(session_id, "session ID"),
        "type": "llm",
        "emotion": _nonempty(emotion, "LLM emotion"),
        "text": str(text),
    }


def server_tts(session_id: str, state: str, text: Optional[str] = None) -> Dict[str, Any]:
    if state not in {"start", "sentence_start", "stop"}:
        raise _static_error("unsupported server TTS state")
    message = {
        "session_id": _nonempty(session_id, "session ID"),
        "type": "tts",
        "state": state,
    }
    if state == "sentence_start":
        message["text"] = _nonempty(text, "TTS sentence")
    elif text is not None:
        raise _static_error("server TTS state must not include text")
    return message


def serialize_server_message(message: Mapping[str, Any]) -> str:
    return json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_binary_frame(payload: bytes) -> bytes:
    if not isinstance(payload, bytes):
        raise _static_error("terminal binary frame must be bytes")
    if not payload:
        raise _static_error("terminal binary frame must not be empty")
    if len(payload) > MAX_BINARY_FRAME_BYTES:
        raise _static_error("terminal binary frame is too large")
    return payload


class TerminalSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = _nonempty(session_id, "session ID")
        self.state = TerminalState.AWAITING_HELLO
        self.generation = 0
        self.active_generation: Optional[int] = None

    def _require_state(self, *states: TerminalState) -> None:
        if self.state not in states:
            raise TerminalStateError("terminal event is invalid in the current state")

    def _require_session(self, control: ClientControl) -> None:
        if not hmac.compare_digest(control.session_id, self.session_id):
            raise TerminalStateError("terminal session ID does not match")

    def accept_hello(self, hello: ClientHello) -> Dict[str, Any]:
        self._require_state(TerminalState.AWAITING_HELLO)
        if hello.version != PROTOCOL_VERSION or hello.transport != TRANSPORT:
            raise TerminalStateError("terminal hello is incompatible")
        if hello.audio != UPLINK_AUDIO:
            raise TerminalStateError("terminal hello audio is incompatible")
        self.state = TerminalState.IDLE
        return server_hello(self.session_id)

    def accept_control(self, control: ClientControl) -> Optional[int]:
        self._require_state(
            TerminalState.IDLE,
            TerminalState.LISTENING,
            TerminalState.PROCESSING,
            TerminalState.SPEAKING,
        )
        self._require_session(control)
        if control.message_type == "listen" and control.state == "start":
            self._require_state(TerminalState.IDLE)
            self.generation += 1
            self.active_generation = self.generation
            self.state = TerminalState.LISTENING
            return self.active_generation
        if control.message_type == "listen" and control.state == "stop":
            self._require_state(TerminalState.LISTENING)
            self.state = TerminalState.PROCESSING
            return self.active_generation
        if control.message_type == "abort":
            self._require_state(
                TerminalState.LISTENING,
                TerminalState.PROCESSING,
                TerminalState.SPEAKING,
            )
            self._invalidate()
            self.state = TerminalState.IDLE
            return None
        if control.message_type == "goodbye":
            self._invalidate()
            self.state = TerminalState.CLOSED
            return None
        raise TerminalStateError("unsupported terminal control event")

    def _invalidate(self) -> None:
        self.generation += 1
        self.active_generation = None

    def is_current_generation(self, generation: int) -> bool:
        return self.active_generation == generation

    def accept_uplink_audio(self, payload: bytes) -> Optional[bytes]:
        if self.state != TerminalState.LISTENING:
            return None
        return validate_binary_frame(payload)

    def begin_speaking(self, generation: int) -> None:
        self._require_state(TerminalState.PROCESSING)
        if not self.is_current_generation(generation):
            raise TerminalStateError("terminal generation is stale")
        self.state = TerminalState.SPEAKING

    def release_downlink_audio(
        self, generation: int, payload: bytes
    ) -> Optional[bytes]:
        if self.state != TerminalState.SPEAKING:
            return None
        if not self.is_current_generation(generation):
            return None
        return validate_binary_frame(payload)

    def complete_speaking(self, generation: int) -> None:
        self._require_state(TerminalState.SPEAKING)
        if not self.is_current_generation(generation):
            raise TerminalStateError("terminal generation is stale")
        self.active_generation = None
        self.state = TerminalState.IDLE

    def disconnect(self) -> None:
        if self.state != TerminalState.CLOSED:
            self._invalidate()
            self.state = TerminalState.CLOSED
