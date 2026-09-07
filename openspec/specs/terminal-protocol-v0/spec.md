# Terminal Protocol v0

## Purpose

Define the authenticated XiaoZhi-compatible header, JSON control, audio negotiation, server message, raw Opus, and compatibility-fixture contract for terminal protocol draft v0.

## Requirements

### Requirement: Authenticated version-one handshake
Protocol draft v0 SHALL require protocol version 1, a non-empty device ID, a non-empty client ID, and a bearer authorization header; configured token comparison MUST be constant-time and parsed identity or validation errors MUST NOT expose the token.

#### Scenario: Valid device headers
- **WHEN** a device presents the required version, identity, and matching bearer token
- **THEN** the parser returns protocol, device, and client identity without retaining the credential

#### Scenario: Invalid credential
- **WHEN** authorization is absent, malformed, or differs from the configured token
- **THEN** handshake validation fails with a static secret-free error

### Requirement: Bounded XiaoZhi hello negotiation
Protocol draft v0 SHALL accept a device hello only when it declares version 1, WebSocket transport, raw Opus, 16 kHz mono uplink, and 60 ms frames, and SHALL produce a server hello declaring the same transport and 24 kHz mono 60 ms Opus downlink.

#### Scenario: Compatible hello
- **WHEN** a valid draft-v0 device hello is received
- **THEN** the server response contains the assigned session ID and canonical downlink audio parameters

#### Scenario: Unsupported audio profile
- **WHEN** format, sample rate, channel count, frame duration, transport, or version differs
- **THEN** the hello is rejected before any audio is accepted

### Requirement: Strict voice control messages
The protocol codec SHALL validate device `listen`, `abort`, and `goodbye` messages with required session and state fields and SHALL reject malformed JSON, unknown types, unsupported modes, and unexpected fields needed for neither compatibility nor optional upstream features.

#### Scenario: Manual listen lifecycle
- **WHEN** valid session-bound listen start and stop messages are parsed
- **THEN** typed control messages preserve their lifecycle state and manual mode

#### Scenario: Unknown control type
- **WHEN** a text frame declares an unsupported message type
- **THEN** protocol validation fails with no state transition

### Requirement: Canonical server messages
The codec SHALL build stable server hello, STT, LLM emotion, and TTS start, sentence-start, and stop JSON objects with the active session ID.

#### Scenario: TTS lifecycle serialization
- **WHEN** a response begins, a sentence is announced, and audio completes
- **THEN** canonical TTS messages are serialized in start, sentence-start, stop order

### Requirement: Raw bounded Opus frames
Protocol draft v0 SHALL treat each version-one binary WebSocket payload as an opaque non-empty Opus frame within the configured maximum size and MUST NOT prepend project-specific metadata.

#### Scenario: Valid raw frame
- **WHEN** a non-empty payload within the maximum is received
- **THEN** the exact bytes cross the codec unchanged

#### Scenario: Empty or oversized frame
- **WHEN** a binary payload is empty or exceeds the maximum
- **THEN** it is rejected without decoding

### Requirement: Executable compatibility fixtures
The repository SHALL include non-secret draft-v0 request and response fixtures that are validated by automated tests and identify their upstream release baseline.

#### Scenario: Fixture regression
- **WHEN** the protocol compatibility suite runs offline
- **THEN** every fixture parses or serializes to the documented canonical shape without network or hardware
