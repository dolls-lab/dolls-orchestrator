## Why

The offline WAV-to-WAV baseline is complete, but a user still cannot speak through the desktop microphone or exercise the future DeepSeek protocol without replacing placeholder code. The next Phase 1 increment should make the desktop experience interactive and make API enablement a credentials-and-configuration step while preserving a no-network default.

## What Changes

- Replace the DeepSeek placeholder with a complete Chat Completions SSE adapter that is disabled by default and fully testable through an injected transport.
- Add push-to-talk desktop recording to mono 16 kHz PCM WAV and automatic local playback of generated replies.
- Add an interactive multi-turn CLI that retains bounded context, exposes clear listening/thinking/playing states, supports cancellation and clean exit, and can run entirely without an API key.
- Add a microphone-independent test harness and opt-in hardware smoke checks so CI remains deterministic.
- Record API request metadata and usage without logging credentials or full conversation content.

## Capabilities

### New Capabilities

- `deepseek-streaming`: Disabled-by-default DeepSeek V4 Flash Chat Completions integration with non-thinking SSE output, normalized errors, usage capture, cancellation, and injectable transport tests.
- `desktop-interactive-session`: Push-to-talk recording, automatic playback, state feedback, multi-turn CLI control, and a no-API interactive profile.

### Modified Capabilities

None.

## Impact

- Adds optional desktop audio dependencies and platform adapters under `src/dolls_orchestrator`.
- Replaces the intentional DeepSeek placeholder while retaining the same normalized LLM contract and explicit network guard.
- Extends the CLI with an interactive command; existing `run-turn` behavior remains compatible.
- No API request is made during implementation or automated verification because no key is supplied and network remains disabled.
