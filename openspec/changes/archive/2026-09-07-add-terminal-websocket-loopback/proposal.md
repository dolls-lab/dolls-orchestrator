## Why

The terminal protocol draft is executable only as an in-process codec, so it cannot yet prove that real WebSocket handshakes, text frames, binary frames, cancellation, and disconnect cleanup preserve the protocol contract. A loopback transport is the next independently testable step before hardware or model integration.

## What Changes

- Add an authenticated asyncio WebSocket server adapter for the draft-v0 terminal endpoint.
- Bridge connection frames to the existing terminal codec and lifecycle state machine through an injected, provider-independent turn handler.
- Bound per-turn buffered uplink audio and normalize protocol, handler, cancellation, and disconnect closure behavior.
- Add a real localhost WebSocket integration suite covering handshake rejection, a successful half-duplex exchange, abort, stale output suppression, and reconnect isolation.
- Add a Python 3.9-compatible optional terminal transport dependency and document installation and security boundaries.

## Capabilities

### New Capabilities
- `terminal-websocket-transport`: Authenticated WebSocket serving, frame routing, response delivery, bounded buffering, and loopback verification.

### Modified Capabilities
- `terminal-session-lifecycle`: Require transport-level response work to be cancelled and stale output suppressed after abort or disconnect.

## Impact

- Adds `terminal_transport` runtime code and transport-focused tests.
- Adds `websockets>=15,<16` as an optional `terminal` dependency compatible with the repository's Python 3.9 floor.
- Reuses the existing protocol codec without changing the draft-v0 wire format.
- Does not add Opus decoding, model loading, microphone access, cloud API calls, LAN exposure by default, or a production deployment command.
