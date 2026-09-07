## MODIFIED Requirements

### Requirement: Bounded local conversation context
The orchestrator SHALL build each LLM request from one active character system instruction, the active package's immutable example pairs when present, recent user and assistant messages stored locally, and the current user message. It SHALL send at most the configured number of completed runtime turns while retaining character instructions and examples.

#### Scenario: Context exceeds the turn limit
- **WHEN** a successful turn would make stored runtime context exceed the configured limit
- **THEN** the oldest complete runtime turn is removed while character system instructions and examples remain available

#### Scenario: Package examples are active
- **WHEN** a loaded character package contains example pairs
- **THEN** they appear after the system instruction and before bounded runtime conversation messages in declared order

### Requirement: Privacy-preserving telemetry
The system SHALL record stage durations, end-to-end duration, selected provider and model versions, active character ID and package version, token usage when available, and terminal status without recording secrets, raw audio content, package paths, prompts, examples, or source-claim text.

#### Scenario: Successful telemetry record
- **WHEN** a turn completes with a loaded character package
- **THEN** one structured summary contains identifiers, character ID and version, provider versions, measurements, usage, and success status

#### Scenario: Error telemetry record
- **WHEN** a turn fails after startup
- **THEN** the summary contains the normalized error type, stage, and non-sensitive character metadata without API credentials or character content
