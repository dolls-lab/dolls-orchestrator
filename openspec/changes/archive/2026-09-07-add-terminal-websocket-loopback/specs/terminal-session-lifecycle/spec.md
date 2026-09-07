## ADDED Requirements

### Requirement: Transport-owned response cancellation
The WebSocket transport SHALL keep response work owned by its connection and MUST cancel it when abort, goodbye, or disconnect invalidates the active generation.

#### Scenario: Abort while handler is running
- **WHEN** a client aborts after listen stop while its turn handler is still awaiting completion
- **THEN** the handler is cancelled, the session returns to idle, and no later response text or audio is sent for that generation

#### Scenario: Disconnect while handler is running
- **WHEN** the connection closes while response work is active
- **THEN** the handler is cancelled and all output for that session is permanently suppressed
