## Context

The repository exposes four adapter profiles with different prerequisites: fully offline adapters, macOS commands, MLX Python packages/model configuration, and guarded DeepSeek credentials/network access. Today the only way to discover a missing prerequisite is to start a turn and fail inside ASR, LLM, or TTS. A future LAN service needs a predictable preflight suitable for startup checks and diagnostics.

The user is not enabling DeepSeek or participating in manual testing now. Health checks must therefore be structural and local: they report whether configuration and local executable/import prerequisites are present without proving model quality, opening a microphone, downloading weights, synthesizing audio, or contacting a provider.

## Goals / Non-Goals

**Goals:**

- Give every built-in adapter a normalized, side-effect-free readiness result.
- Aggregate selected character, ASR, LLM, and TTS components in stable stage order.
- Distinguish ready from blocked components with bounded machine-readable reason codes.
- Report every component even when one is blocked and return an overall readiness status.
- Add a CLI preflight that is safe to run before deployment or API setup.

**Non-Goals:**

- Testing microphone/speaker permissions, downloading or loading MLX model weights, or transcribing audio.
- Calling DeepSeek, validating a live API key, measuring latency, or checking provider quota.
- Running TTS commands or judging audio/role quality.
- Replacing runtime errors and telemetry from real turns.

## Decisions

### Normalized adapter health contract

`AdapterHealth` contains stage, provider, model, status, and an optional bounded reason code. Built-in adapter protocols expose synchronous `health()` because every check in this phase is local and non-blocking. Status is `ready` or `blocked`; there is no ambiguous “healthy network” claim.

Alternative: infer readiness from adapter class names in the CLI. Rejected because deployment and future server code need a provider-independent contract, and adapter-owned checks remain correct when construction changes.

### Side-effect-free local checks

Offline adapters always report ready. macOS TTS checks `say` and `afconvert` discovery only. MLX Whisper checks import discovery for `mlx_whisper` and `numpy`, unless an injected runner already supplies the implementation. DeepSeek checks only the explicit network flag and key presence; both present means configuration-ready, not provider-verified.

Alternative: execute smoke requests. Rejected because it would consume API/resources, require user setup, and make health checks unsafe for routine startup.

### Aggregated character and profile report

A new service readiness module resolves the character package separately, then calls the three adapter health contracts in character/ASR/LLM/TTS order. Character validation failure becomes a blocked component with a generic reason code, while remaining adapters are still reported. The report never includes the package path, prompts, examples, key state value, or exception message.

### CLI exit semantics

`health` accepts the same profile choices and optional character path resolution as dialogue commands. It prints one JSON document. Exit zero means every component is ready under the structural checks; exit one means one or more components are blocked; malformed application configuration remains exit two.

## Risks / Trade-offs

- [Import discovery does not prove the MLX model is cached or runnable] → Use reason/status wording “ready” only for declared preflight scope and document that first real ASR remains a separate test.
- [A present DeepSeek key may be invalid] → Never label the remote provider reachable; only report configuration readiness without sending data.
- [Command discovery does not prove voice availability] → Retain runtime synthesis checks and document the boundary.
- [Adapter protocol changes affect test fakes] → Python structural typing is not enforced at runtime; only built-in profile adapters are required by this change.

## Migration Plan

1. Add normalized health domain data and built-in adapter methods.
2. Add report aggregation and CLI coverage.
3. Use `health --profile offline` as the deployment baseline.
4. Later expose the same report through a local health endpoint when the WebSocket service is added.

Rollback removes the health command and methods without changing primary adapter operations.

## Open Questions

- Should a later active probe be a distinct command so routine readiness can remain side-effect free?
