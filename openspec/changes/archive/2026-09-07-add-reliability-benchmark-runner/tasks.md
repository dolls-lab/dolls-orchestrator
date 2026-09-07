## 1. Turn measurement

- [x] 1.1 Add optional end-to-end first-audio latency to turn telemetry serialization.
- [x] 1.2 Record first-audio latency exactly once on the first accepted TTS chunk across success and failure paths.

## 2. Benchmark runner

- [x] 2.1 Implement sequential repeated-turn execution with failure isolation and cancellation propagation.
- [x] 2.2 Implement deterministic percentile, success-rate, and immediate-recovery aggregation.
- [x] 2.3 Implement versioned privacy-safe report serialization and atomic writing.
- [x] 2.4 Add the validated `benchmark-turns` CLI command and exit semantics.

## 3. Verification and documentation

- [x] 3.1 Add telemetry, percentile, failure recovery, privacy, atomic report, and CLI tests.
- [x] 3.2 Document the measurement boundary, offline usage, report schema, and deferred thresholds.
- [x] 3.3 Run the full suite, compile/package checks, strict OpenSpec validation, secret scan, and diff checks.
