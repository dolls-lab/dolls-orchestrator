## Context

The terminal protocol fixes uplink audio at raw Opus, 16 kHz, mono, 60 ms and downlink audio at raw Opus, 24 kHz, mono, 60 ms. `OrchestratorTerminalBridge` already exposes an asynchronous codec boundary, but only test doubles implement it. The project must remain usable without cloud credentials, and codec state must be isolated between terminal turns.

## Goals / Non-Goals

**Goals:**

- Implement the codec boundary against the native, reference `libopus` API.
- Preserve packet order and codec state for the duration of one encode or decode operation.
- Accept the orchestrator's signed 16-bit mono PCM and resample it deterministically when its sample rate differs from the terminal target.
- Produce stable, secret-safe application errors and support dependency discovery without importing a Python wrapper.
- Exercise the real codec through the existing localhost WebSocket transport and offline adapters.

**Non-Goals:**

- Ogg/WebM containers, packet-loss concealment, forward error correction, jitter buffering, or network packet reordering.
- Streaming partial orchestration responses or retaining codec state across turns.
- Bundling or downloading `libopus` at runtime.
- Supporting stereo or PCM sample widths other than signed 16-bit.

## Decisions

### Bind directly to `libopus` with `ctypes`

The module will load a caller-supplied library path, the platform library lookup result, or common Homebrew paths, then bind the small encoder/decoder API surface. This avoids a Python wrapper dependency while retaining the reference codec implementation. A pure-Python Opus implementation was rejected as too large and risky; invoking `ffmpeg` was rejected because subprocess/container framing obscures the raw packet contract.

### Scope native state to one operation

Each `decode_uplink` call creates one decoder and consumes packets in sequence; each `encode_downlink` call creates one encoder and emits frames in sequence. Both destroy native state in `finally` blocks. This matches Opus state semantics while preventing one terminal turn from influencing another.

### Keep the async boundary non-blocking

Native encode/decode and resampling execute in `asyncio.to_thread`. The public methods remain compatible with `TerminalAudioCodec` and do not block the event loop during longer audio turns.

### Use deterministic mono PCM resampling and fixed frame padding

Signed 16-bit mono samples are linearly interpolated when source and target rates differ. Output is divided into exact 60 ms frames, with only the final incomplete frame padded with silence. This lightweight baseline is sufficient for speech-loop validation; a production-quality resampler can replace it behind the same boundary later.

### Normalize failures at the codec boundary

Unsupported formats, missing libraries, invalid PCM, corrupt packets, and negative native return codes become `OpusCodecError` with stage `terminal_audio_codec`. Messages do not include payloads, tokens, library search paths, or native pointers.

## Risks / Trade-offs

- [Linear interpolation can reduce audio quality] → Restrict it to the current mono speech baseline and test duration/energy; retain a replaceable internal resampling function.
- [Raw Opus has no container metadata or pre-skip field] → Treat each WebSocket binary message as one packet and document that the receiver relies on negotiated audio parameters.
- [Native libraries vary by platform] → Support explicit injection and common discovery paths, expose a deterministic availability check, and fail before processing audio.
- [Malformed native inputs could be expensive] → Enforce packet size, frame duration, channel, sample-rate, and PCM-alignment limits before calling `libopus`.

## Migration Plan

1. Install `libopus` through the host package manager.
2. Construct `LibOpusCodec` and inject it into the existing terminal bridge.
3. Run native unit and localhost loopback tests before enabling a terminal service runner.
4. Roll back by returning to another `TerminalAudioCodec` implementation; no protocol or persisted data migration is required.

## Open Questions

None for this baseline. Jitter handling, PLC/FEC, and a higher-quality resampler remain later production-hardening work.
