## Context

The orchestrator currently supports desktop WAV and microphone flows only. The project design requires a XiaoZhi-compatible WebSocket protocol draft v0 during phase two, before physical Atom VoiceS3R testing freezes protocol v1. Upstream `xiaozhi-esp32` v2.4.2 documents a version-1 WebSocket handshake, JSON control frames, and raw Opus binary frames, while also warning server implementers to cross-check actual firmware behavior.

This change must establish executable semantics without a device, socket listener, Opus codec, or new dependency. It therefore separates pure protocol parsing/state from later network and audio transport work.

## Goals / Non-Goals

**Goals:**

- Record a bounded draft v0 aligned with the upstream v2.4.2 WebSocket documentation.
- Validate handshake identity and bearer credentials without retaining or logging secrets.
- Validate device hello, listen, abort, goodbye, and raw binary-frame boundaries.
- Produce canonical server hello, STT, LLM emotion, and TTS lifecycle messages.
- Enforce a deterministic server-side session state machine and reject stale-generation audio.
- Provide fixtures and compatibility tests reusable by a later WebSocket server and `dolls-terminal`.

**Non-Goals:**

- Opening a TCP/WebSocket port or choosing a WebSocket library.
- Encoding, decoding, resampling, or playing Opus audio.
- Supporting upstream binary protocol versions 2/3, MCP, AEC, wake words, OTA, or IoT control.
- Claiming a frozen protocol v1 or verified compatibility with physical Atom VoiceS3R firmware.
- Selecting Wi-Fi provisioning, TLS certificate, or production token storage mechanisms.

## Decisions

### Versioned narrow compatibility slice

Draft v0 accepts upstream protocol version 1, `transport=websocket`, Opus, mono, 16 kHz uplink, 24 kHz downlink, and 60 ms frames. Binary frames remain untouched raw Opus payloads. The source pin is `xiaozhi-esp32` release v2.4.2 (`e8d8a40` as displayed by GitHub); the document records that upstream main has advanced and hardware verification is outstanding.

Alternative: copy every current upstream message and binary version. Rejected because unneeded MCP/UI/AEC features would enlarge the attack and compatibility surface before the basic voice path is tested.

### Pure codec and state machine

One standard-library module owns immutable protocol models, JSON parsing/building, header authentication, binary-frame bounds, and `TerminalSession`. Network code added later will adapt WebSocket frames to this module rather than owning duplicate business state.

Alternative: implement a WebSocket server immediately. Rejected because the repository has no selected server dependency, and socket behavior would obscure the protocol contract during offline testing.

### Secret-safe handshake identity

The parser requires protocol, device, client, and bearer headers. When an expected device token is supplied, comparison uses `hmac.compare_digest`. Returned identity excludes the bearer value, and all validation errors use static messages without header contents.

### Connection-scoped generation semantics

The session moves through `awaiting_hello`, `idle`, `listening`, `processing`, `speaking`, and `closed`. Each accepted listen start allocates a monotonically increasing generation. Abort and disconnect invalidate the generation before returning to idle/closed. Uplink audio is accepted only while listening; downlink audio is emitted only while speaking for the current generation. Stale data is dropped rather than raising into a network loop.

Alternative: put a custom generation header inside each Opus frame. Rejected because upstream version 1 uses raw Opus and the project design explicitly defers custom framing until real tests show it is necessary.

### Checked-in compatibility fixtures

Compact JSON fixtures capture representative upstream messages and expected server messages. Tests load these files through the public codec, verify stable serialization, and exercise state transitions. They are protocol examples, not recordings or private device data.

## Risks / Trade-offs

- [Upstream v2.4.2 behavior differs from the Atom VoiceS3R build] → Label the contract draft v0 and keep real-firmware discrepancies as a required later change.
- [A strict 16/24 kHz and 60 ms slice rejects other valid XiaoZhi configurations] → Prefer one reproducible MVP profile now; add negotiated profiles only after evidence from target hardware.
- [No socket test proves only domain compatibility] → Add a loopback WebSocket transport as a separate offline change after this contract is archived.
- [Connection-scoped generations cannot identify stale bytes already buffered on the device] → Pair server invalidation with device buffer clear during real integration; reconsider framing only if misplay remains.

## Migration Plan

1. Land pure protocol and state-machine contracts with fixtures.
2. Build a loopback WebSocket adapter against the same public API.
3. Reuse fixtures in `dolls-terminal` host-side compatibility tests.
4. Test the pinned firmware on Atom VoiceS3R and record discrepancies.
5. Freeze protocol v1 only after cancellation, disconnect, and stale-audio tests pass on hardware.

Rollback removes the new isolated module and fixtures; existing desktop flows are unaffected.

## Open Questions

- Does the target board artifact use the upstream `atom-echos3r` identifier despite the project name “Atom VoiceS3R”?
- Will the actual v2.4.2 device accept 24 kHz downlink with 60 ms frames without additional configuration?
