## Context

`dolls-orchestrator` currently contains requirements but no executable service. The first milestone must prove the desktop WAV-to-WAV path while the user intentionally withholds API credentials. The development host is Apple Silicon macOS with built-in `say` and `afconvert`; Python 3.12 and MLX tooling are expected to be supplied through a managed environment later. Raw audio must remain local, and the eventual terminal, character package, and role TTS integrations need stable boundaries rather than dependencies on a provider SDK.

## Goals / Non-Goals

**Goals:**

- Establish testable ASR, streaming LLM, and streaming TTS contracts.
- Run a deterministic offline WAV-to-WAV vertical slice without credentials or model downloads.
- Provide concrete MLX Whisper, DeepSeek, and macOS speech adapter boundaries that fail safely when prerequisites are absent.
- Implement generation-aware cancellation, bounded context, incremental sentence scheduling, typed recovery, and privacy-safe telemetry.
- Make later real-provider enablement a configuration change plus adapter implementation rather than an orchestration rewrite.

**Non-Goals:**

- Sending a live DeepSeek request in this change.
- Downloading or benchmarking a Whisper model.
- Capturing live microphone input or building a graphical desktop client.
- Producing the target character voice, loading a formal character package, or implementing the terminal WebSocket protocol.
- Long-term memory, persistence, authentication, or multi-user service behavior.

## Decisions

### Async contracts with a sequential turn owner

Adapters use async methods and async iterators so provider streams can be consumed without redesign. A single `TurnOrchestrator` owns each turn and is the only component allowed to commit context or audio. This makes cancellation and stale-generation checks enforceable in one place. A concurrent graph or message broker was rejected because it adds lifecycle complexity before there is more than one user.

### Domain types remain provider independent

Dataclasses and protocols represent audio, ASR results, LLM deltas, synthesis chunks, identifiers, errors, and telemetry. Provider response objects are converted at adapter boundaries. This costs a small amount of mapping code but prevents DeepSeek or MLX SDK changes from leaking into session behavior.

### Deterministic offline profile is the executable baseline

The offline profile uses a WAV-validating fake ASR, a chunked scripted LLM, and a deterministic PCM tone TTS. It exercises the same contracts as real adapters and guarantees CI can verify the full pipeline without network access, credentials, macOS voices, or model weights. A `local-no-api` profile replaces the audio edges with MLX Whisper and macOS speech while keeping the scripted LLM, allowing every non-API component to be exercised together. Tests alone with mocked orchestrator methods were rejected because they would not prove output assembly.

### DeepSeek is disabled by default

The placeholder accepts model, base URL, output limit, thinking mode, and an environment-only API key. It checks both an explicit network-enable flag and the key before provider invocation. The initial implementation deliberately raises a typed configuration error even when enabled, documenting the remaining integration point without accidentally sending user text.

### Apple-specific speech adapters are optional edges

MLX Whisper is represented by an injectable command runner so its result parsing and errors can be tested without importing or downloading a model. The macOS TTS adapter invokes `say` and converts output with `afconvert`, isolated behind the TTS protocol. The default offline profile is portable; the local-voice profile clearly reports missing platform prerequisites.

### Sentence-level audio is assembled by the runner

The splitter emits Chinese sentence boundaries and a maximum-character fallback. TTS audio for each sentence is normalized as mono 16-bit PCM at a configured sample rate, and the runner writes one standard WAV container. This baseline favors correctness and simple playback over immediate audio streaming; a later transport can forward the same chunks as they arrive.

### Context is explicit and local

The session stores only completed user/assistant pairs and retains a configurable maximum of six turns. Failed and cancelled replies are never committed. DeepSeek is stateless, so this also preserves provider portability and makes user-controlled clearing straightforward.

### Standard-library core with optional integrations

The runnable offline core and tests use the Python standard library. Python 3.12 is declared for the project, while MLX integration is an optional extra. This avoids blocking the first verified slice on package installation and still allows `uv` to manage the intended environment later.

## Risks / Trade-offs

- [Fake ASR does not measure recognition quality] → Keep its telemetry clearly labeled and require a separate MLX baseline before ASR acceptance.
- [System TTS is not the target character voice] → Treat it only as an integration fallback and preserve the streaming TTS contract for `dolls-voice`.
- [Sentence-by-sentence WAV normalization can add latency] → Measure each synthesis call and replace file conversion with streaming PCM when integrating the terminal.
- [Subprocess cancellation may leave a child briefly alive] → Terminate and await child processes in adapter cleanup; stale generation checks remain the final output guard.
- [DeepSeek compatibility can change before enablement] → Keep provider code isolated, record the configured model, and add opt-in contract tests when credentials are supplied.
- [Short context can omit useful details] → Make the complete-turn limit configurable and measure character behavior before adding summaries or long-term memory.

## Migration Plan

1. Land the offline contracts, runner, tests, and documentation.
2. Run the deterministic profile and retain its telemetry as the first baseline.
3. Install Python 3.12/MLX dependencies and download a selected Whisper model outside this change, then run ASR contract tests.
4. Implement and explicitly enable the live DeepSeek call after the user provides the environment variable.
5. Replace macOS speech with the versioned `dolls-voice` service without changing orchestration contracts.

Rollback consists of selecting the offline profile or reverting this initial code; the change has no persistent data migration or external side effect.

## Open Questions

- The verified MLX baseline uses `mlx-community/whisper-small-mlx` revision `45f3915923c7a79a5a5b5a7d909d39aeb0e5630e`; a later performance change can revise it through an explicit comparison.
- The temporary macOS Chinese voice can change without affecting the TTS contract.
- Formal role-quality thresholds remain owned by the later `dolls-character` integration change.
