## Why

The WebSocket transport can exchange protocol frames but still has no concrete handler that turns terminal audio into an orchestrated voice turn. A codec-neutral bridge is required before choosing an Opus implementation or connecting hardware.

## What Changes

- Add an asynchronous terminal audio codec contract for decoding ordered 16 kHz Opus frames to normalized PCM and encoding orchestrator PCM to ordered 24 kHz Opus frames.
- Add a transport turn handler that validates codec output, writes a private per-turn temporary WAV, invokes `TurnOrchestrator`, and maps its result to the canonical terminal response.
- Preserve transport cancellation semantics across the orchestrator's normalized cancellation error and delete temporary audio on success, failure, or cancellation.
- Add deterministic unit and real localhost WebSocket integration tests without a real Opus library, model, microphone, device, or API.

## Capabilities

### New Capabilities
- `terminal-audio-orchestration-bridge`: Codec-neutral terminal audio conversion, orchestration invocation, response mapping, cancellation, and temporary-data cleanup.

### Modified Capabilities

None.

## Impact

- Adds a `terminal_bridge` module and bridge/integration tests.
- Reuses `TerminalTurnHandler`, `TurnOrchestrator`, existing WAV helpers, and protocol audio parameters.
- Adds no runtime dependency and makes no selection of an Opus codec implementation.
- Does not expose a LAN service command or claim hardware, acoustic, or real audio compatibility.
