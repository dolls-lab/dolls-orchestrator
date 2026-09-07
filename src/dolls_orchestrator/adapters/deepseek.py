"""Guarded DeepSeek Chat Completions streaming adapter."""

import asyncio
from dataclasses import dataclass, field
import json
import threading
import time
from typing import Any, AsyncIterator, Mapping, Optional, Protocol, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from ..domain import LLMEvent, TurnContext
from ..errors import ProviderConfigurationError, ProviderUnavailableError


@dataclass(frozen=True)
class SSERequest:
    url: str
    headers: Mapping[str, str] = field(repr=False)
    payload: Mapping[str, Any]
    timeout_seconds: float


class TransportHTTPError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__("HTTP %d" % status)
        self.status = status


class SSETransport(Protocol):
    def stream(self, request: SSERequest) -> AsyncIterator[str]:
        ...


class UrllibSSETransport:
    """Bridge a blocking urllib response into an async line iterator."""

    async def stream(self, request: SSERequest) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()
        response_holder = []
        sentinel = object()

        def worker() -> None:
            try:
                body = json.dumps(request.payload, ensure_ascii=False).encode("utf-8")
                http_request = urlrequest.Request(
                    request.url,
                    data=body,
                    headers=dict(request.headers),
                    method="POST",
                )
                with urlrequest.urlopen(http_request, timeout=request.timeout_seconds) as response:
                    response_holder.append(response)
                    for raw_line in response:
                        if stop.is_set():
                            break
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            raw_line.decode("utf-8", "replace").rstrip("\r\n"),
                        )
            except urlerror.HTTPError as exc:
                loop.call_soon_threadsafe(queue.put_nowait, TransportHTTPError(exc.code))
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        worker_task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield str(item)
            await worker_task
        finally:
            stop.set()
            if response_holder:
                response_holder[0].close()
            if not worker_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(worker_task), 1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass


class DeepSeekLLMAdapter:
    provider = "deepseek"

    def __init__(
        self,
        api_key: Optional[str],
        base_url: str,
        model: str,
        network_enabled: bool,
        max_output_tokens: int,
        timeout_seconds: float = 30.0,
        transport: Optional[SSETransport] = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.network_enabled = network_enabled
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.transport = transport or UrllibSSETransport()

    async def stream_reply(
        self, messages: Sequence[Mapping[str, str]], context: TurnContext
    ) -> AsyncIterator[LLMEvent]:
        if not self.network_enabled:
            raise ProviderConfigurationError(
                "DeepSeek network access is disabled; set DOLLS_DEEPSEEK_NETWORK_ENABLED=true only when ready"
            )
        if not self._api_key:
            raise ProviderConfigurationError(
                "DEEPSEEK_API_KEY is required when DeepSeek network access is enabled"
            )
        sse_request = SSERequest(
            url=self.base_url + "/chat/completions",
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            payload={
                "model": self.model,
                "messages": [dict(message) for message in messages],
                "thinking": {"type": "disabled"},
                "stream": True,
                "stream_options": {"include_usage": True},
                "max_tokens": self.max_output_tokens,
            },
            timeout_seconds=self.timeout_seconds,
        )
        started = time.perf_counter()
        actual_model = self.model
        usage = {}
        finish_reason = None
        try:
            async for line in self.transport.stream(sse_request):
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderUnavailableError(
                        "DeepSeek returned malformed SSE JSON", stage="llm"
                    ) from exc
                if isinstance(payload.get("error"), dict):
                    code = payload["error"].get("code", "provider_error")
                    raise ProviderUnavailableError(
                        "DeepSeek stream error: %s" % code, stage="llm"
                    )
                choices = payload.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ProviderUnavailableError(
                        "DeepSeek returned an unsupported SSE event", stage="llm"
                    )
                choice = choices[0]
                if not isinstance(choice, dict):
                    raise ProviderUnavailableError(
                        "DeepSeek returned an unsupported choice", stage="llm"
                    )
                delta = choice.get("delta") or {}
                if not isinstance(delta, dict):
                    raise ProviderUnavailableError(
                        "DeepSeek returned an unsupported delta", stage="llm"
                    )
                content = delta.get("content")
                if content:
                    yield LLMEvent(kind="text_delta", text=str(content))
                if choice.get("finish_reason") is not None:
                    finish_reason = str(choice["finish_reason"])
                if payload.get("model"):
                    actual_model = str(payload["model"])
                if isinstance(payload.get("usage"), dict):
                    usage = {
                        str(key): int(value)
                        for key, value in payload["usage"].items()
                        if isinstance(value, (int, float))
                    }
        except TransportHTTPError as exc:
            if exc.status in (401, 403):
                raise ProviderConfigurationError(
                    "DeepSeek authentication was rejected (HTTP %d)" % exc.status
                ) from exc
            if exc.status == 429:
                raise ProviderUnavailableError(
                    "DeepSeek rate limit reached (HTTP 429)", stage="llm"
                ) from exc
            if exc.status >= 500:
                raise ProviderUnavailableError(
                    "DeepSeek service unavailable (HTTP %d)" % exc.status,
                    stage="llm",
                ) from exc
            raise ProviderUnavailableError(
                "DeepSeek request failed (HTTP %d)" % exc.status, stage="llm"
            ) from exc
        except (ProviderConfigurationError, ProviderUnavailableError):
            raise
        except (TimeoutError, urlerror.URLError) as exc:
            raise ProviderUnavailableError(
                "DeepSeek connection timed out or is unavailable", stage="llm"
            ) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        metadata = {"finish_reason": finish_reason} if finish_reason else {}
        yield LLMEvent(
            kind="completed",
            metadata=metadata,
            provider=self.provider,
            model=actual_model,
            usage=usage,
            elapsed_ms=elapsed_ms,
        )


# Backward-compatible import name used by the first milestone.
DeepSeekPlaceholderAdapter = DeepSeekLLMAdapter
