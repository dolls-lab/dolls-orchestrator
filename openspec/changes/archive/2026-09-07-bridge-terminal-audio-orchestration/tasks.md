## 1. Codec and Bridge Contracts

- [x] 1.1 Add immutable decoded-audio data and the asynchronous terminal codec protocol
- [x] 1.2 Add a bounded terminal audio bridge error type and canonical format validation

## 2. Orchestration Bridge

- [x] 2.1 Implement private temporary WAV creation and connection-session orchestration invocation
- [x] 2.2 Implement transcript, reply, neutral emotion, and validated downlink frame mapping
- [x] 2.3 Preserve cancellation across `TurnCancelledError` and guarantee temporary-data cleanup

## 3. Offline Verification

- [x] 3.1 Add bridge unit tests for successful mapping, exact codec inputs, format rejection, output rejection, failure, and cleanup
- [x] 3.2 Add cancellation tests proving active orchestration stops and no response survives
- [x] 3.3 Add a real localhost WebSocket-to-offline-orchestrator test with a synthetic codec

## 4. Documentation and Delivery

- [x] 4.1 Document the bridge boundary, audio contracts, privacy behavior, and remaining real Opus work
- [x] 4.2 Run dependency-free and installed-extra suites, compile, Wheel, secret, diff, and strict OpenSpec checks
- [x] 4.3 Sync the new capability spec, archive the change, create one commit, and push
