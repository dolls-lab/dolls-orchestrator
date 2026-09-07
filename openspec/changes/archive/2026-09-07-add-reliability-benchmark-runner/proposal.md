## Why

The target design requires independent records of continuous-turn success rate, P50/P95 first-audio latency, and recovery after failures, but current telemetry only exposes per-stage timing and no repeatable aggregate runner. An offline benchmark baseline can close this measurement gap without API credentials or physical hardware.

## What Changes

- Record end-to-end time from turn start to the first synthesized audio chunk.
- Add a sequential multi-turn benchmark runner over the existing orchestrator and WAV input contract.
- Produce an atomic, versioned, privacy-preserving JSON report with success rate, nearest-rank P50/P95 first-audio and total latency, and post-failure recovery counts.
- Add a `benchmark-turns` CLI command for offline and future real profiles.
- Continue after individual turn failures while preserving cancellation semantics.
- Document what the baseline measures and defer product pass/fail thresholds until user/device evidence exists.

## Capabilities

### New Capabilities

- `reliability-benchmark-runner`: Continuous turn execution, aggregation, report contract, failure isolation, and CLI behavior.

### Modified Capabilities

- `turn-orchestration`: Add end-to-end first-audio latency to privacy-preserving turn telemetry.

## Impact

- Extends `TurnTelemetry` with one optional measurement and updates orchestration timing.
- Adds a standard-library benchmark/report module, CLI command, tests, and documentation.
- Does not add network access, model dependencies, audio-device use, or acceptance thresholds.
