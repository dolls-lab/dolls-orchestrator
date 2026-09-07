## Why

The project currently defines the desktop voice proof of concept only in requirements and has no executable orchestration baseline. A deterministic local-first vertical slice is needed now to validate adapter boundaries, turn lifecycle, cancellation, recovery, and audio output before credentials or production model services are introduced.

## What Changes

- Add a Python 3.12 application skeleton for the orchestration service and command-line desktop turn runner.
- Define provider-independent ASR, streaming LLM, and streaming TTS contracts plus shared turn events and error types.
- Add a local MLX Whisper ASR adapter, a macOS `say` TTS adapter, and a configurable DeepSeek LLM placeholder that makes no network request until explicitly enabled with credentials.
- Add deterministic fake adapters so the complete WAV-to-WAV pipeline can run and be tested without API access or downloaded model weights.
- Add bounded short-term conversation context, sentence segmentation, generation-aware cancellation, timeouts, and failure recovery.
- Add structured per-turn telemetry for stage latency, configuration versions, and token usage without logging secrets or raw audio.

## Capabilities

### New Capabilities

- `adapter-contracts`: Provider-independent ASR, streaming LLM, and streaming TTS interfaces with common results, events, cancellation, and error semantics.
- `turn-orchestration`: A generation-aware desktop voice-turn pipeline with bounded context, sentence segmentation, timeouts, cancellation, recovery, and telemetry.
- `desktop-turn-runner`: A CLI that accepts a WAV file, runs a selected adapter profile, writes a playable WAV response, and supports an offline deterministic profile plus placeholder production configuration.

### Modified Capabilities

None.

## Impact

- Adds the initial runtime code, tests, packaging, and configuration under `dolls-orchestrator`.
- Introduces Python dependencies for application configuration, testing, and optional Apple Silicon speech recognition.
- Uses built-in macOS `say` and `afconvert` for the temporary local voice path.
- Establishes contracts later consumed by `dolls-character`, `dolls-voice`, and `dolls-terminal`; no external repository is modified by this change.
- No DeepSeek request is sent in this change. The API key remains an environment-only future input.
