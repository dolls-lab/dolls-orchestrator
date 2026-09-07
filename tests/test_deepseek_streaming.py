import asyncio
import json
import unittest

from dolls_orchestrator.adapters.deepseek import (
    DeepSeekLLMAdapter,
    TransportHTTPError,
)
from dolls_orchestrator.domain import TurnContext
from dolls_orchestrator.errors import ProviderConfigurationError, ProviderUnavailableError


CONTEXT = TurnContext("session", "turn", "generation")
MESSAGES = [{"role": "user", "content": "你好"}]


class FakeTransport:
    def __init__(self, lines=(), error=None):
        self.lines = list(lines)
        self.error = error
        self.requests = []
        self.closed = False

    async def stream(self, request):
        self.requests.append(request)
        try:
            if self.error:
                raise self.error
            for line in self.lines:
                await asyncio.sleep(0)
                yield line
        finally:
            self.closed = True


def adapter(transport, key="test-secret", enabled=True):
    return DeepSeekLLMAdapter(
        api_key=key,
        base_url="https://api.deepseek.com/",
        model="deepseek-v4-flash",
        network_enabled=enabled,
        max_output_tokens=256,
        transport=transport,
    )


class DeepSeekStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_guard_does_not_call_transport(self):
        transport = FakeTransport()
        stream = adapter(transport, enabled=False).stream_reply(MESSAGES, CONTEXT)
        with self.assertRaises(ProviderConfigurationError):
            await stream.__anext__()
        self.assertEqual([], transport.requests)

    async def test_missing_key_does_not_call_transport(self):
        transport = FakeTransport()
        stream = adapter(transport, key=None).stream_reply(MESSAGES, CONTEXT)
        with self.assertRaises(ProviderConfigurationError):
            await stream.__anext__()
        self.assertEqual([], transport.requests)

    async def test_request_shape_and_stream_output(self):
        lines = [
            ": keep-alive",
            "data: " + json.dumps(
                {
                    "model": "DeepSeek-V4-Flash-0731",
                    "choices": [{"delta": {"content": "你好"}, "finish_reason": None}],
                },
                ensure_ascii=False,
            ),
            "data: " + json.dumps(
                {
                    "model": "DeepSeek-V4-Flash-0731",
                    "choices": [{"delta": {"content": "呀！"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
                },
                ensure_ascii=False,
            ),
            "data: [DONE]",
        ]
        transport = FakeTransport(lines)
        events = [event async for event in adapter(transport).stream_reply(MESSAGES, CONTEXT)]
        self.assertEqual(["你好", "呀！"], [event.text for event in events[:-1]])
        self.assertEqual("completed", events[-1].kind)
        self.assertEqual("DeepSeek-V4-Flash-0731", events[-1].model)
        self.assertEqual(15, events[-1].usage["total_tokens"])
        self.assertEqual("stop", events[-1].metadata["finish_reason"])
        request = transport.requests[0]
        self.assertEqual("https://api.deepseek.com/chat/completions", request.url)
        self.assertEqual("Bearer test-secret", request.headers["Authorization"])
        self.assertEqual(MESSAGES, request.payload["messages"])
        self.assertTrue(request.payload["stream"])
        self.assertEqual({"type": "disabled"}, request.payload["thinking"])
        self.assertEqual(256, request.payload["max_tokens"])
        self.assertNotIn("test-secret", repr(request))

    async def test_malformed_sse_is_normalized(self):
        transport = FakeTransport(["data: not-json"])
        with self.assertRaisesRegex(ProviderUnavailableError, "malformed"):
            async for _ in adapter(transport).stream_reply(MESSAGES, CONTEXT):
                pass

    async def test_http_errors_are_normalized_without_secret(self):
        for status, error_type, text in (
            (401, ProviderConfigurationError, "authentication"),
            (429, ProviderUnavailableError, "rate limit"),
            (503, ProviderUnavailableError, "unavailable"),
        ):
            with self.subTest(status=status):
                transport = FakeTransport(error=TransportHTTPError(status))
                with self.assertRaises(error_type) as captured:
                    async for _ in adapter(transport).stream_reply(MESSAGES, CONTEXT):
                        pass
                self.assertIn(text, str(captured.exception))
                self.assertNotIn("test-secret", str(captured.exception))

    async def test_cancellation_closes_transport(self):
        class SlowTransport(FakeTransport):
            async def stream(self, request):
                self.requests.append(request)
                try:
                    yield 'data: {"choices":[{"delta":{"content":"开"},"finish_reason":null}]}'
                    await asyncio.sleep(10)
                finally:
                    self.closed = True

        transport = SlowTransport()

        async def consume():
            async for _ in adapter(transport).stream_reply(MESSAGES, CONTEXT):
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.02)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(transport.closed)


if __name__ == "__main__":
    unittest.main()
