## Context

The first change established a verified WAV-to-WAV pipeline, local MLX Whisper transcription, macOS speech synthesis, cancellation semantics, and a DeepSeek placeholder. The remaining Phase 1 gap is an actual desktop conversation loop and a production-shaped DeepSeek stream implementation. The user will provide the key later, so implementation and verification must make zero API requests. The current target is Apple Silicon macOS and half-duplex push-to-talk.

## Goals / Non-Goals

**Goals:**

- Implement current DeepSeek V4 Flash Chat Completions SSE semantics behind the existing LLM protocol.
- Preserve an explicit two-part network guard: enable flag plus environment-only key.
- Record microphone audio in the ASR format and automatically play synthesized replies.
- Support repeated interactive turns, clear state feedback, clean cancellation, and retry after failure.
- Test all decision logic through injected boundaries without external services or audio hardware.

**Non-Goals:**

- Sending a real DeepSeek request during this change.
- Voice activity detection, wake words, full duplex, echo cancellation, or playback interruption by speech.
- Graphical UI, mobile client, terminal WebSocket protocol, formal character package, or target voice.
- Persisting conversation history or recordings after the process exits.

## Decisions

### Retain Chat Completions and explicit local context

DeepSeek currently supports both Chat Completions and Responses. Chat Completions maps directly to the existing message-list protocol and returns data-only SSE deltas. The adapter sends full bounded context because DeepSeek calls are stateless. Responses was considered but adds no benefit to this text-only, tool-free milestone.

### Disable thinking mode for spoken dialogue

Requests include `thinking: {"type": "disabled"}` and a small output limit. DeepSeek enables thinking by default, but spoken character dialogue prioritizes first-token latency and concise replies. Reasoning mode can later become a separate profile rather than silently changing latency.

### Use an injectable SSE transport with a standard-library production implementation

The adapter consumes an async line transport. The production transport runs `urllib.request` streaming in one worker thread and bridges lines into an asyncio queue; tests inject a deterministic in-memory transport. This keeps the standard-library core installable and allows response closing on cancellation. Adding a full HTTP client dependency was rejected for a single guarded endpoint.

### Use optional `sounddevice` for microphone capture

`sounddevice.RawInputStream` provides 16-bit PCM frames directly and supports CoreAudio device selection. It is isolated behind a recorder protocol and included in a desktop optional dependency group. A custom Swift helper and FFmpeg capture were rejected because they add build/runtime processes and duplicate lifecycle logic.

### Keep playback as a subprocess edge

macOS `afplay` accepts the output WAV and naturally blocks for half-duplex playback. The player adapter terminates its child on cancellation. Tests inject a fake player, and `--no-playback` supports headless validation.

### Model the interactive loop separately from argparse

An `InteractiveSession` owns prompts, temporary files, session reuse, turn execution, playback, and retry. Console input, recorder, player, and output sink are injected. The CLI only constructs dependencies, which keeps behavior testable without patching global input or devices.

### Keep recordings ephemeral

Each turn uses a temporary directory that is deleted after playback or failure. The command prints transcript and reply for the local user but structured telemetry excludes both. A later explicit debug-retention option would require a separate privacy decision.

## Risks / Trade-offs

- [Microphone permission prompts cannot be automated reliably] → Provide device listing and actionable permission errors; verify device discovery separately and keep deterministic fake-recorder tests.
- [Blocking URL streams run in a worker thread] → Close the response on cancellation, use bounded queues, and configure socket timeouts; replace with a native async client only if concurrency grows.
- [SSE error bodies may contain sensitive prompt echoes] → Do not expose raw bodies; log only status category and provider error code where safe.
- [System playback may be unavailable in remote/headless sessions] → Support `--no-playback` and keep WAV output validation independent.
- [Keyboard Enter is not a physical push button] → Treat it as the Phase 1 desktop control; terminal hardware owns the later button state machine.

## Migration Plan

1. Add and test DeepSeek request construction, SSE parsing, error mapping, and cancellation with fake transport.
2. Add recorder/player protocols and deterministic implementations for tests.
3. Add optional `sounddevice` capture and macOS `afplay` playback.
4. Add and test the interactive `chat` command with `local-no-api` as the default safe profile.
5. Verify microphone device discovery and a local no-API turn where host permissions allow.
6. When the user later supplies a key, enable the network flag for an explicit smoke test and record a separate baseline.

Rollback is selection of the existing `run-turn` command and offline profiles. No persistent migration is required.

## Open Questions

- The preferred physical microphone device may need explicit selection after device enumeration.
- The live DeepSeek latency baseline remains unknown until the user enables the API.
