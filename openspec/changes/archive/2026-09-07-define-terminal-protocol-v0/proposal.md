## Why

The desktop orchestration path is executable, but the service has no terminal-facing protocol contract, so Atom VoiceS3R work cannot be simulated or regression-tested before hardware access. Phase two requires a XiaoZhi-compatible protocol draft now, while real-device validation remains unavailable and protocol v1 must stay unfrozen.

## What Changes

- Define protocol draft v0 against the upstream `xiaozhi-esp32` v2.4.2 WebSocket behavior, using protocol version 1 raw Opus framing.
- Add strict, secret-safe validation for handshake headers, device hello, listen lifecycle, abort, goodbye, and binary audio boundaries.
- Add server-message builders for hello, STT, LLM emotion, and TTS lifecycle events.
- Add an in-memory terminal session state machine with explicit connection, listening, processing, speaking, abort, disconnect, and generation invalidation semantics.
- Add protocol fixtures, deterministic compatibility tests, and documentation of upstream pins and unverified hardware assumptions.
- Exclude network socket serving and Opus encoding/decoding; those remain later changes built on this contract.

## Capabilities

### New Capabilities
- `terminal-protocol-v0`: Versioned XiaoZhi-compatible header, JSON-control, audio-parameter, and raw Opus frame contract.
- `terminal-session-lifecycle`: Server-side terminal state transitions, cancellation, disconnect recovery, and stale-generation audio rejection.

### Modified Capabilities

None.

## Impact

The change adds a standard-library protocol module, JSON fixtures, tests, and a draft specification document in `dolls-orchestrator`. It introduces no runtime dependency, opens no network listener, performs no model/API call, and does not claim compatibility with physical hardware until a later device test.
