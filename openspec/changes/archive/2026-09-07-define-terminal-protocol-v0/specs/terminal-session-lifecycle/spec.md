## ADDED Requirements

### Requirement: Explicit terminal session states
The server-side terminal session SHALL transition only through awaiting-hello, idle, listening, processing, speaking, and closed states according to valid protocol events.

#### Scenario: Successful half-duplex turn
- **WHEN** hello, listen start, uplink audio, listen stop, response start, downlink audio, and response completion occur in order
- **THEN** the session reaches idle after visiting every applicable state

#### Scenario: Out-of-order event
- **WHEN** a valid message is incompatible with the current state
- **THEN** the session rejects it without changing state or generation

### Requirement: Directional audio gating
The session SHALL accept uplink binary audio only while listening and SHALL release downlink binary audio only while speaking for the current generation.

#### Scenario: Audio in wrong state
- **WHEN** uplink audio arrives while idle or downlink audio is offered before speaking
- **THEN** the payload is dropped and no state changes

### Requirement: Generation invalidation
Each accepted listen start SHALL allocate a newer generation, and abort, disconnect, or a newer turn MUST invalidate outputs belonging to any prior generation.

#### Scenario: Abort during speaking
- **WHEN** the active generation is aborted and an old downlink frame arrives later
- **THEN** the session is idle and drops that stale frame

#### Scenario: New turn after abort
- **WHEN** listening starts again after abort
- **THEN** the new generation is greater than the aborted generation

### Requirement: Session identity enforcement
After hello, every session-bound control message MUST match the assigned session ID and a mismatch MUST NOT mutate lifecycle state.

#### Scenario: Foreign session control
- **WHEN** a listen or abort message carries another session ID
- **THEN** the message is rejected and the current session remains unchanged

### Requirement: Disconnect closure
Disconnect or goodbye SHALL invalidate active work and close the connection-scoped session so later control and audio frames cannot be accepted.

#### Scenario: Disconnect during processing
- **WHEN** transport disconnects while a generation is processing
- **THEN** that generation becomes stale and the session transitions to closed
