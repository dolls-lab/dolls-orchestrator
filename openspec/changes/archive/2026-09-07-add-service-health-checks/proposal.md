## Why

The orchestrator has multiple adapter profiles and a character-package boundary, but operators cannot determine readiness without attempting a full turn. Phase-two deployment and later terminal serving need a side-effect-free preflight that distinguishes local dependency gaps from deliberately disabled API access.

## What Changes

- Add a provider-independent adapter health result and `health()` contract for built-in ASR, LLM, and TTS adapters.
- Add side-effect-free readiness checks for offline adapters, MLX Whisper imports, macOS commands, and DeepSeek configuration guards.
- Add a service health report that combines character-package validity with the selected profile's ASR, LLM, and TTS readiness.
- Add a `health` CLI command with stable JSON output and zero/non-zero readiness exit semantics.
- Guarantee that preflight does not download models, open audio devices, run synthesis, or make network/API requests.

## Capabilities

### New Capabilities
- `service-readiness`: Aggregated, secret-safe, side-effect-free character and adapter readiness reporting.

### Modified Capabilities
- `adapter-contracts`: Require built-in adapters to expose normalized readiness without performing their primary operation.
- `desktop-turn-runner`: Add a profile-aware health command and exit semantics for local deployment preflight.

## Impact

The change extends normalized domain contracts, built-in adapters, profiles, CLI, tests, and documentation. It adds no dependency and does not alter the execution behavior of existing turn, chat, character, evaluation, or terminal-protocol paths.
