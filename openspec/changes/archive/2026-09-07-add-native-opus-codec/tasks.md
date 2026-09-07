## 1. Native codec boundary

- [x] 1.1 Add the normalized codec error and deterministic `libopus` discovery/version reporting.
- [x] 1.2 Implement validated operation-scoped raw-Opus decoding.
- [x] 1.3 Implement PCM validation, deterministic mono resampling, 60 ms padding, and raw-Opus encoding.

## 2. Verification

- [x] 2.1 Add native unit tests for discovery, validation, decoding, encoding, padding, resampling, and corrupt packets.
- [x] 2.2 Add a real Opus localhost WebSocket loopback test using offline orchestration adapters.
- [x] 2.3 Run the complete test suite, compile/package checks, OpenSpec validation, secret scan, and diff checks.

## 3. Documentation

- [x] 3.1 Document system dependency installation, discovery behavior, raw-packet framing, and current limitations.
