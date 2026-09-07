# Turn Orchestration

## Purpose

Define the generation-aware voice-turn lifecycle, bounded context, incremental synthesis scheduling, recovery, and telemetry.

## Requirements

### Requirement: Generation-aware turn lifecycle
The orchestrator SHALL assign each turn a session ID, turn ID, and generation ID and SHALL transition it through listening-input, transcribing, generating, synthesizing, completed, cancelled, or failed states.

#### Scenario: Successful voice turn
- **WHEN** each configured stage succeeds
- **THEN** the turn completes with ordered reply text, playable audio, and terminal completion telemetry

#### Scenario: New turn supersedes old output
- **WHEN** a newer generation starts for the same session
- **THEN** text and audio produced by the older generation are not delivered

### Requirement: Bounded local conversation context
The orchestrator SHALL build each LLM request from one active character system instruction, the active package's immutable example pairs when present, recent user and assistant messages stored locally, and the current user message. It SHALL send at most the configured number of completed runtime turns while retaining character instructions and examples.

#### Scenario: Context exceeds the turn limit
- **WHEN** a successful turn would make stored context exceed the configured limit
- **THEN** the oldest complete runtime turn is removed while character system instructions and examples remain available

#### Scenario: Package examples are active
- **WHEN** a loaded character package contains example pairs
- **THEN** they appear after the system instruction and before bounded runtime conversation messages in declared order

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
The system SHALL record stage durations, end-to-end duration, selected provider and model versions, active character ID and package version, token usage when available, and terminal status without recording secrets, raw audio content, package paths, prompts, examples, or source-claim text.

#### Scenario: Successful telemetry record
- **WHEN** a turn completes with a loaded character package
- **THEN** one structured summary contains identifiers, character ID and version, provider versions, measurements, usage, and success status

#### Scenario: Error telemetry record
- **WHEN** a turn fails after startup
- **THEN** the summary contains the normalized error type, stage, and non-sensitive character metadata without API credentials or character content
