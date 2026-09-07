## Context

The transport now supplies one immutable turn containing authenticated identity and ordered opaque uplink frames. `TurnOrchestrator` accepts a WAV path and returns accumulated PCM with an `AudioFormat`. The missing layer is format conversion and lifecycle translation between these contracts. No real Opus implementation or hardware is available, and the bridge must remain usable with every existing adapter profile.

## Goals / Non-Goals

**Goals:**

- Define one replaceable async codec contract around canonical uplink and downlink audio parameters.
- Convert a terminal turn into the existing WAV input contract without changing ASR adapters.
- Convert orchestrator output into validated terminal frames and canonical response fields.
- Preserve abort/disconnect cancellation and remove all temporary PCM/WAV data on every outcome.
- Prove the whole transport-to-orchestrator boundary with deterministic local adapters and synthetic frames.

**Non-Goals:**

- Selecting or implementing libopus, FFmpeg, resampling, streaming ASR, sentence-level downlink streaming, or real-time latency optimization.
- Changing the terminal wire protocol, `TurnOrchestrator` adapter contracts, or profile behavior.
- Starting a LAN service, using a microphone, or calling a provider API.

## Decisions

### Model codec conversion as an asynchronous protocol

`TerminalAudioCodec.decode_uplink` accepts the ordered opaque frames plus canonical uplink parameters and returns immutable PCM bytes with `AudioFormat`. `encode_downlink` accepts orchestrator PCM/source format plus canonical downlink parameters and returns ordered opaque frames. Async methods let a future implementation use subprocesses, threads, or streaming libraries without blocking the event loop. A concrete fake codec stays in tests rather than production.

### Keep temporary WAV ownership inside the bridge

The bridge validates non-empty decoded PCM and exact 16 kHz mono signed-16 PCM, creates a private `TemporaryDirectory`, writes `input.wav`, and passes that path to the unchanged orchestrator. The context manager removes the file on success, codec failure, orchestrator failure, or cancellation. Changing all ASR adapters to accept in-memory PCM was rejected because it expands an unrelated stable contract.

### Preserve terminal session identity and use neutral emotion

The bridge invokes `run_turn` with the WebSocket session ID so context, supersession, and telemetry stay connection-scoped. It maps transcript and reply directly, uses a bounded `neutral` emotion until structured emotion metadata exists, and returns validated encoded frames. Device/client identity is not added to prompts or telemetry.

### Translate normalized orchestrator cancellation back to task cancellation

`TurnOrchestrator` intentionally converts `asyncio.CancelledError` into `TurnCancelledError`. At the transport boundary, the bridge catches that normalized error and raises `asyncio.CancelledError` again. This lets the connection-owned response task treat abort/disconnect as expected cancellation instead of an internal failure that closes the socket with 1011.

## Risks / Trade-offs

- [Whole-turn buffering prevents streaming ASR and increases latency] → Keep existing strict transport byte limits and treat streaming conversion as a later measured optimization.
- [Exact 16 kHz decoded PCM rejects codecs that internally resample] → Require the codec to normalize its output explicitly so ASR input is deterministic.
- [One accumulated reply maps to one TTS sentence event] → Preserve canonical ordering now; introduce sentence/audio correlation only with a streaming orchestrator result contract.
- [Synthetic codec tests cannot establish Opus correctness] → Name fixtures and reports synthetic and retain draft-v0/hardware validation gates.

## Migration Plan

The bridge is additive. Existing WebSocket tests can keep injecting handlers, while integrated callers instantiate the bridge with an orchestrator and codec. Rollback removes the module without changing protocol, packages, or persisted state.

## Open Questions

- Which maintained Opus binding supports the target macOS/Linux deployment and required 16/24 kHz frame sizes.
- Whether ASR should eventually consume decoded PCM incrementally rather than a completed WAV.
- How sentence-level TTS metadata and encoded frames will be emitted without accumulating the full turn.
