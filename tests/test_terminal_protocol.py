import json
from pathlib import Path
import unittest

from dolls_orchestrator.errors import TerminalProtocolError, TerminalStateError
from dolls_orchestrator.terminal_protocol import (
    DRAFT_VERSION,
    DOWNLINK_AUDIO,
    MAX_BINARY_FRAME_BYTES,
    UPSTREAM_COMMIT,
    UPSTREAM_RELEASE,
    ClientControl,
    ClientHello,
    TerminalSession,
    TerminalState,
    parse_client_text,
    serialize_server_message,
    server_hello,
    server_llm,
    server_stt,
    server_tts,
    validate_binary_frame,
    validate_handshake_headers,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "terminal_protocol_v0.json"


def _text(value):
    return json.dumps(value, ensure_ascii=False)


class TerminalProtocolCodecTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_handshake_identity_excludes_token(self):
        token = "test-device-token"
        identity = validate_handshake_headers({
            "Authorization": "Bearer " + token,
            "Protocol-Version": "1",
            "Device-Id": "device-01",
            "Client-Id": "client-01",
        }, expected_token=token)
        self.assertEqual(1, identity.protocol_version)
        self.assertEqual("device-01", identity.device_id)
        self.assertNotIn(token, repr(identity))

    def test_invalid_handshake_errors_are_static_and_secret_free(self):
        secret = "do-not-print-this-token"
        headers = {
            "Authorization": "Bearer " + secret,
            "Protocol-Version": "1",
            "Device-Id": "device-01",
            "Client-Id": "client-01",
        }
        with self.assertRaises(TerminalProtocolError) as raised:
            validate_handshake_headers(headers, expected_token="different-token")
        self.assertNotIn(secret, str(raised.exception))
        self.assertEqual("terminal_protocol", raised.exception.stage)

        for key in ("Authorization", "Device-Id", "Client-Id"):
            incomplete = dict(headers)
            incomplete.pop(key)
            with self.assertRaises(TerminalProtocolError):
                validate_handshake_headers(incomplete)

    def test_hello_and_controls_parse_to_typed_models(self):
        hello = parse_client_text(_text(self.fixture["client"]["hello"]))
        self.assertIsInstance(hello, ClientHello)
        self.assertEqual(16000, hello.audio.sample_rate)

        start = parse_client_text(_text(self.fixture["client"]["listen_start"]))
        stop = parse_client_text(_text(self.fixture["client"]["listen_stop"]))
        abort = parse_client_text(_text(self.fixture["client"]["abort"]))
        goodbye = parse_client_text(_text(self.fixture["client"]["goodbye"]))
        self.assertEqual(("start", "manual"), (start.state, start.mode))
        self.assertEqual("stop", stop.state)
        self.assertEqual("user_cancelled", abort.reason)
        self.assertEqual("goodbye", goodbye.message_type)

    def test_malformed_unknown_and_unsupported_messages_fail(self):
        invalid_values = [
            "{",
            "[]",
            _text({"type": "unknown"}),
            _text({"type": "hello", "version": 2, "transport": "websocket", "audio_params": {}}),
            _text({
                "type": "listen",
                "session_id": "fixture-session",
                "state": "start",
                "mode": "unsupported",
            }),
            _text({
                "type": "listen",
                "session_id": "fixture-session",
                "state": "stop",
                "extra": True,
            }),
        ]
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(TerminalProtocolError):
                parse_client_text(value)

        incompatible = dict(self.fixture["client"]["hello"])
        incompatible["audio_params"] = dict(incompatible["audio_params"])
        incompatible["audio_params"]["sample_rate"] = 24000
        with self.assertRaisesRegex(TerminalProtocolError, "uplink audio"):
            parse_client_text(_text(incompatible))

    def test_server_builders_match_canonical_fixtures(self):
        expected = self.fixture["server"]
        actual = {
            "hello": server_hello("fixture-session"),
            "stt": server_stt("fixture-session", "你好"),
            "llm": server_llm("fixture-session", "happy", "😀"),
            "tts_start": server_tts("fixture-session", "start"),
            "tts_sentence": server_tts(
                "fixture-session", "sentence_start", "你好呀！"
            ),
            "tts_stop": server_tts("fixture-session", "stop"),
        }
        self.assertEqual(expected, actual)
        for message in actual.values():
            serialized = serialize_server_message(message)
            self.assertEqual(message, json.loads(serialized))
            self.assertNotIn(" ", serialized)
        self.assertEqual(24000, DOWNLINK_AUDIO.sample_rate)

    def test_binary_frame_is_raw_and_bounded(self):
        frame = b"\x01\x02opus"
        self.assertIs(frame, validate_binary_frame(frame))
        for invalid in (b"", b"x" * (MAX_BINARY_FRAME_BYTES + 1), bytearray(b"x")):
            with self.subTest(size=len(invalid)), self.assertRaises(TerminalProtocolError):
                validate_binary_frame(invalid)

    def test_fixture_identifies_upstream_baseline(self):
        self.assertEqual(DRAFT_VERSION, self.fixture["draft_version"])
        self.assertEqual(UPSTREAM_RELEASE, self.fixture["upstream"]["release"])
        self.assertEqual(UPSTREAM_COMMIT, self.fixture["upstream"]["commit"])
        for message in self.fixture["client"].values():
            self.assertIsNotNone(parse_client_text(_text(message)))


class TerminalSessionTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.client = fixture["client"]
        self.hello = parse_client_text(_text(self.client["hello"]))
        self.start = parse_client_text(_text(self.client["listen_start"]))
        self.stop = parse_client_text(_text(self.client["listen_stop"]))
        self.abort = parse_client_text(_text(self.client["abort"]))
        self.goodbye = parse_client_text(_text(self.client["goodbye"]))

    def ready_session(self):
        session = TerminalSession("fixture-session")
        response = session.accept_hello(self.hello)
        self.assertEqual("fixture-session", response["session_id"])
        self.assertEqual(TerminalState.IDLE, session.state)
        return session

    def test_successful_half_duplex_flow(self):
        session = self.ready_session()
        generation = session.accept_control(self.start)
        self.assertEqual(TerminalState.LISTENING, session.state)
        self.assertEqual(b"uplink", session.accept_uplink_audio(b"uplink"))
        self.assertEqual(generation, session.accept_control(self.stop))
        self.assertEqual(TerminalState.PROCESSING, session.state)
        session.begin_speaking(generation)
        self.assertEqual(b"downlink", session.release_downlink_audio(
            generation, b"downlink"
        ))
        session.complete_speaking(generation)
        self.assertEqual(TerminalState.IDLE, session.state)
        self.assertIsNone(session.active_generation)

    def test_out_of_order_events_do_not_mutate_state_or_generation(self):
        session = TerminalSession("fixture-session")
        with self.assertRaises(TerminalStateError):
            session.accept_control(self.start)
        self.assertEqual(TerminalState.AWAITING_HELLO, session.state)
        self.assertEqual(0, session.generation)

        session.accept_hello(self.hello)
        with self.assertRaises(TerminalStateError):
            session.accept_control(self.stop)
        self.assertEqual(TerminalState.IDLE, session.state)
        self.assertEqual(0, session.generation)
        self.assertIsNone(session.accept_uplink_audio(b"late"))

    def test_foreign_session_control_is_rejected_without_mutation(self):
        session = self.ready_session()
        foreign = ClientControl(
            message_type="listen",
            session_id="foreign",
            state="start",
            mode="manual",
        )
        with self.assertRaisesRegex(TerminalStateError, "does not match"):
            session.accept_control(foreign)
        self.assertEqual(TerminalState.IDLE, session.state)
        self.assertEqual(0, session.generation)

    def test_abort_invalidates_generation_and_drops_stale_audio(self):
        session = self.ready_session()
        first = session.accept_control(self.start)
        session.accept_control(self.stop)
        session.begin_speaking(first)
        session.accept_control(self.abort)
        self.assertEqual(TerminalState.IDLE, session.state)
        self.assertFalse(session.is_current_generation(first))
        self.assertIsNone(session.release_downlink_audio(first, b"stale"))

        second = session.accept_control(self.start)
        self.assertGreater(second, first)

    def test_disconnect_and_goodbye_close_session(self):
        session = self.ready_session()
        generation = session.accept_control(self.start)
        session.accept_control(self.stop)
        session.disconnect()
        self.assertEqual(TerminalState.CLOSED, session.state)
        self.assertFalse(session.is_current_generation(generation))
        self.assertIsNone(session.release_downlink_audio(generation, b"stale"))
        with self.assertRaises(TerminalStateError):
            session.accept_control(self.start)

        session = self.ready_session()
        session.accept_control(self.goodbye)
        self.assertEqual(TerminalState.CLOSED, session.state)


if __name__ == "__main__":
    unittest.main()
