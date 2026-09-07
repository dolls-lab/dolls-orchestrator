## ADDED Requirements

### Requirement: Generation-aware turn lifecycle
The orchestrator SHALL assign each turn a session ID, turn ID, and generation ID and SHALL transition it through listening-input, transcribing, generating, synthesizing, completed, cancelled, or failed states.

#### Scenario: Successful voice turn
- **WHEN** each configured stage succeeds
- **THEN** the turn completes with ordered reply text, playable audio, and terminal completion telemetry

#### Scenario: New turn supersedes old output
- **WHEN** a newer generation starts for the same session
- **THEN** text and audio produced by the older generation are not delivered

### Requirement: Bounded local conversation context
The orchestrator SHALL maintain recent user and assistant messages locally and SHALL send at most the configured number of completed turns to the LLM adapter.

#### Scenario: Context exceeds the turn limit
- **WHEN** a successful turn would make stored context exceed the configured limit
- **THEN** the oldest complete turn is removed while system character instructions remain available

### Requirement: Incremental sentence scheduling
The orchestrator SHALL detect sentence boundaries in streamed Chinese text and SHALL submit complete sentences to TTS in source order, with a configurable length fallback for text lacking punctuation.

#### Scenario: First sentence arrives before reply completion
- **WHEN** a complete sentence is observed while the LLM is still streaming
- **THEN** synthesis for that sentence begins without waiting for the full reply

#### Scenario: Stream ends with an incomplete sentence
- **WHEN** the LLM stream ends with remaining non-empty text
- **THEN** the remainder is submitted once as the final sentence

### Requirement: Timeout and failure recovery
Each external stage SHALL have a configured timeout, and failure of one turn MUST NOT prevent a later turn from running.

#### Scenario: Stage timeout
- **WHEN** a stage exceeds its timeout
- **THEN** the turn ends with a typed failure and all pending work for that generation is cancelled

#### Scenario: Retry after failure
- **WHEN** a new turn starts after a prior turn failed
- **THEN** the new turn executes from a clean generation state

### Requirement: Privacy-preserving telemetry
The system SHALL record stage durations, end-to-end duration, selected provider and model versions, token usage when available, and terminal status without recording secrets or raw audio content.

#### Scenario: Successful telemetry record
- **WHEN** a turn completes
- **THEN** one structured summary contains identifiers, versions, measurements, usage, and success status

#### Scenario: Error telemetry record
- **WHEN** a turn fails
- **THEN** the summary contains the normalized error type and stage without containing API credentials

