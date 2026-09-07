## 1. Transport Contract and Dependency

- [x] 1.1 Add immutable terminal turn request/response models and an async handler contract
- [x] 1.2 Add the Python 3.9-compatible optional WebSocket transport dependency without changing the offline core install

## 2. WebSocket Connection Runtime

- [x] 2.1 Implement path and draft-v0 header authentication before WebSocket upgrade
- [x] 2.2 Implement text/binary routing, canonical hello, ordered response delivery, and aggregate uplink limits
- [x] 2.3 Implement connection-owned response cancellation, stale-output gating, bounded close errors, and teardown cleanup

## 3. Offline Integration Verification

- [x] 3.1 Add real localhost WebSocket tests for accepted and rejected handshakes and one complete half-duplex response
- [x] 3.2 Add tests for malformed/order/aggregate failures, abort cancellation, disconnect cleanup, and reconnect isolation
- [x] 3.3 Preserve dependency-free core tests and verify the installed terminal extra on Python 3.9

## 4. Documentation and Delivery

- [x] 4.1 Document installation, loopback scope, endpoint, authentication, limits, and hardware/API non-goals
- [x] 4.2 Run the full suite, compile, Wheel, secret scan, diff checks, and strict OpenSpec validation
- [x] 4.3 Sync delta specs, archive the change, create one commit, and push
