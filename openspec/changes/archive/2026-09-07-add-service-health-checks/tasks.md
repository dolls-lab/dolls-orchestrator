## 1. Adapter Health Contract

- [x] 1.1 Add normalized immutable adapter-health domain data and protocol methods
- [x] 1.2 Implement ready health for deterministic offline adapters
- [x] 1.3 Implement side-effect-free MLX import, macOS command, and DeepSeek configuration health checks
- [x] 1.4 Add adapter health tests for ready, dependency/command missing, injected boundaries, and guarded provider states

## 2. Service Readiness and CLI

- [x] 2.1 Implement ordered character, ASR, LLM, and TTS readiness aggregation with generic package failures
- [x] 2.2 Add `health` CLI profile/package selection, stable JSON output, and exit zero/one/two semantics
- [x] 2.3 Add aggregation and CLI tests for offline ready, partial failure, invalid package, local profiles, no network, and secret exclusion

## 3. Delivery and Archive

- [x] 3.1 Document readiness scope, command examples, reason codes, and distinction from active probes
- [x] 3.2 Run offline/full tests, real local preflight commands, compile, Wheel, secret, diff, and strict OpenSpec checks
- [x] 3.3 Sync delta specs, archive the completed change, then create one commit and push
