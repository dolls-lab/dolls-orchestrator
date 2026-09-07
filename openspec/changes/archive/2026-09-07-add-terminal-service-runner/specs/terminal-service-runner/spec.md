## ADDED Requirements

### Requirement: Explicit terminal service assembly
The system SHALL provide one command that assembles the selected adapter profile, resolved character, turn orchestrator, native Opus codec, terminal audio bridge, and WebSocket transport without requiring cloud credentials for the offline profile.

#### Scenario: Offline service construction
- **WHEN** the operator selects the offline profile with all terminal prerequisites present
- **THEN** the command constructs the complete service without model loading, hardware access, or external network requests

### Requirement: Secret-safe terminal authentication configuration
The terminal service MUST require a non-empty bearer token from environment-backed configuration before binding and MUST NOT accept that token as a command-line argument or expose it through output, errors, health data, or settings representation.

#### Scenario: Token is missing
- **WHEN** terminal service startup is requested without a configured bearer token
- **THEN** startup fails before socket binding with a bounded credential-missing result

#### Scenario: Token is configured
- **WHEN** startup and readiness run with a configured token
- **THEN** the exact token is absent from all emitted data and object representations

### Requirement: Safe network binding policy
The terminal service SHALL bind to `127.0.0.1` by default and MUST reject a non-loopback bind address unless the operator explicitly opts into LAN exposure.

#### Scenario: Default startup
- **WHEN** the operator starts the service without host overrides
- **THEN** the listener binds only to the IPv4 loopback address

#### Scenario: Accidental LAN bind
- **WHEN** a non-loopback host is selected without explicit LAN opt-in
- **THEN** startup fails before creating a listening socket

#### Scenario: Intentional LAN bind
- **WHEN** the operator selects a non-loopback host and explicitly enables LAN binding
- **THEN** the service passes the selected address to the authenticated WebSocket transport

### Requirement: Readiness-gated startup
The runner SHALL execute terminal-specific readiness before binding and SHALL start the WebSocket listener only when character, adapters, transport dependency, native codec, and bearer authentication are all ready.

#### Scenario: Blocked prerequisite
- **WHEN** any required terminal component is blocked
- **THEN** startup reports bounded readiness data and does not invoke the server factory

#### Scenario: Successful bind
- **WHEN** all prerequisites are ready and the socket binds successfully
- **THEN** the runner reports a non-secret listening state with profile and address

### Requirement: Graceful terminal service lifecycle
The runner SHALL close the listening server and wait for its closure when shutdown is requested, the runner is cancelled, or a supported termination signal is received.

#### Scenario: Shutdown event
- **WHEN** the runner's shutdown event is set after startup
- **THEN** it closes the server and awaits complete shutdown exactly once

#### Scenario: Cancellation during service wait
- **WHEN** the runner task is cancelled after binding
- **THEN** it closes and awaits the server before propagating cancellation

### Requirement: Assembled offline loopback
The project SHALL verify the runner's real assembly through localhost WebSocket and raw Opus traffic using offline adapters.

#### Scenario: Complete runner turn
- **WHEN** a valid raw-Opus turn is sent to a started offline terminal service
- **THEN** the service returns canonical text events and decodable raw-Opus speech without cloud or hardware access
