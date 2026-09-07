## 1. Protocol Models and Codec

- [x] 1.1 Add immutable protocol identity, audio, hello, and control-message models plus typed errors
- [x] 1.2 Implement secret-safe handshake header validation and constant-time optional token verification
- [x] 1.3 Implement strict client JSON parsing, canonical server message builders, and raw binary frame bounds
- [x] 1.4 Add protocol codec tests for valid messages, malformed inputs, unsupported profiles, stable serialization, and secret redaction

## 2. Terminal Session Lifecycle

- [x] 2.1 Implement the explicit connection-scoped half-duplex terminal state machine
- [x] 2.2 Implement session identity checks, monotonically increasing generations, abort/disconnect invalidation, and directional audio gating
- [x] 2.3 Add state-machine tests for the successful flow, out-of-order events, foreign sessions, cancellation, disconnect, and stale audio

## 3. Compatibility Baseline and Delivery

- [x] 3.1 Add non-secret draft-v0 request/response fixtures and fixture-driven offline compatibility tests
- [x] 3.2 Document the upstream v2.4.2 pin, supported subset, data/security boundary, known hardware unknowns, and later transport work
- [x] 3.3 Run the full suite, compile and Wheel checks, secret scan, diff checks, and strict OpenSpec validation
- [x] 3.4 Sync completed delta specs into main specs and archive the change
