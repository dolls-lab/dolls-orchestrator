## Context

Protocol draft v0 already defines strict header, JSON, binary-frame, session, and generation behavior, but it has no socket-facing adapter. The repository supports Python 3.9 and deliberately keeps its standard-library offline core installable without speech or network packages. Hardware, Opus codecs, and live providers remain unavailable for this change.

## Goals / Non-Goals

**Goals:**

- Exercise the real RFC 6455 opening handshake and frame types on localhost.
- Keep wire validation and lifecycle ownership in the existing protocol module.
- Provide an injected async turn boundary that future orchestration/audio conversion can implement.
- Accept abort and disconnect while turn response work is running, then suppress stale output.
- Keep authentication failures, logs, requests, and test fixtures free of token values.

**Non-Goals:**

- Opus decode/encode, ASR/LLM/TTS execution, production TLS, public/LAN binding defaults, reconnect policy, or device compatibility claims.
- Freezing protocol v1 or adding a second wire format.
- Exposing an incomplete production server CLI before orchestration and Opus conversion are available.

## Decisions

### Use `websockets` 15 as an optional transport dependency

Add a `terminal` extra with `websockets>=15,<16`. Version 15 supports the repository's Python 3.9 floor and the current `websockets.asyncio` API, while 17 requires Python 3.11. The core package imports the dependency lazily so existing standard-library workflows still run without it. A hand-built WebSocket implementation was rejected because framing, handshake, backpressure, ping, and close correctness are not project-specific value.

### Separate wire transport from turn execution

The transport builds an immutable request from authenticated identity, session, generation, and opaque audio frames, then awaits an injected async handler that returns canonical transcript, reply, emotion, and opaque downlink frames. Tests inject deterministic bytes; future integration can decode Opus and invoke the orchestrator without changing the connection contract.

### Authenticate before upgrade and revalidate at connection entry

`process_request` accepts only `/xiaozhi/v1/` and validates draft-v0 headers against a required server token before the upgrade. The handler reconstructs only the non-secret identity from the accepted request. Revalidation keeps direct handler tests and server-library boundaries explicit; neither identity nor errors retain the token.

### Run response delivery as connection-owned work

After `listen/stop`, response production runs in one connection-owned task while the receive loop continues to accept `abort`, `goodbye`, and disconnect. Abort invalidates the generation and cancels response work. Every text or binary output is gated again against the current generation, and connection teardown cancels and awaits outstanding work.

### Bound memory and disable compression

Each frame retains the codec's maximum and the transport additionally limits aggregate buffered uplink bytes per turn. Per-message deflate is disabled because Opus is already compressed and compression adds no value to opaque audio. The server defaults to `127.0.0.1`; LAN exposure must be an explicit later deployment choice.

## Risks / Trade-offs

- [The injected response schema isn't yet the final streaming orchestrator bridge] → Keep it small, immutable, and limited to protocol fields; replace the handler implementation rather than the WebSocket lifecycle.
- [Buffering a complete uplink turn delays ASR and uses memory] → Enforce a strict aggregate bound now; streaming ASR is a later change after Opus decoding exists.
- [Dependency major versions have incompatible Python floors and APIs] → Constrain the optional extra to the verified 15.x line and document the reason.
- [Loopback cannot prove firmware behavior] → Continue labeling protocol v0 as a draft and reserve v1 for Atom VoiceS3R validation.

## Migration Plan

Install `.[terminal]` only for transport work. Existing installs and commands remain unchanged. Rollback consists of removing the optional extra and transport module; no persisted data or wire migration is involved.

## Open Questions

- Whether the target firmware uses `/xiaozhi/v1/` unchanged in the selected build.
- Which Opus library and streaming ASR boundary will consume the buffered frame sequence.
- Which explicit LAN interface, TLS termination, and token provisioning method will be selected for hardware tests.
