## Context

`TurnOrchestrator` already publishes one terminal telemetry object for success, failure, and cancellation, including total and stage durations. TTS first output is currently measured from the first synthesis request rather than from turn input, and there is no runner that aggregates repeated turns. The target requirements call for reproducible continuous-dialogue and recovery evidence, while real API/device thresholds remain undecided.

## Goals / Non-Goals

**Goals:**

- Measure first synthesized audio from the same start point as total turn latency.
- Execute a configured number of turns sequentially in one bounded conversation session.
- Isolate ordinary turn failures, continue later turns, and quantify immediate recovery.
- Emit deterministic percentile and success summaries plus minimal per-turn diagnostics.
- Write reports atomically and keep text, audio, paths, prompts, credentials, and source claims out.

**Non-Goals:**

- Load generation, concurrent-user, network-throughput, or terminal firmware benchmarks.
- Automatic pass/fail thresholds or performance claims for untested hardware/API profiles.
- Persisting generated audio, transcripts, replies, or full exception messages.
- Treating cancellation as a recoverable benchmark case.

## Decisions

### Add `first_audio_ms` to `TurnTelemetry`

The orchestrator will set the field once, when the first accepted TTS audio chunk arrives, using the turn's `total_started` clock. It stays `None` for failure before audio and cancellation. Reusing the existing telemetry record avoids a parallel timing system.

### Run turns sequentially in one session

The benchmark takes one WAV input and executes N turns with a stable benchmark session ID. This exercises bounded conversation growth and clean post-failure generations. Parallel load was rejected because it measures a different multi-user concern outside the single-user product scope.

### Use nearest-rank percentiles over successful measurements

P50 and P95 are selected from sorted successful values using `ceil(p * n) - 1`, rounded only during serialization. Failed turns do not fabricate latency values; counts make the sample size explicit.

### Define immediate recovery conservatively

Every failed turn followed by another attempted turn is a recovery opportunity. It is counted as recovered only when the immediately following turn completes. The runner catches `OrchestratorError`, records normalized telemetry, and continues; task cancellation propagates.

### Keep the report informational

The report has a version, profile, character identity, summary, and ordered turn records. The CLI exits nonzero if turns fail but does not label latency good or bad. Product thresholds require later user/device evidence and are intentionally not invented here.

## Risks / Trade-offs

- [Synthetic offline timings are much faster than real profiles] → Label profile and provider/model identities and prohibit cross-profile claims.
- [First synthesized audio is earlier than terminal playback] → Name and document the measurement boundary; terminal/network playback latency needs hardware instrumentation later.
- [Repeated identical audio is not a representative corpus] → Position this as pipeline reliability infrastructure; allow future callers to extend input selection behind the runner.
- [A report write can be interrupted] → Write a sibling temporary file, fsync through close, and atomically replace the target.

## Migration Plan

The telemetry field is additive and optional, so existing consumers remain valid. Operators can run `benchmark-turns` with the offline profile immediately and later reuse the same command with explicit real profiles. Rollback removes the command and optional field without persisted-state migration.

## Open Questions

Target/acceptable/failure thresholds, representative audio corpus, and terminal playback timestamp collection remain user/device-dependent follow-up decisions.
