## MODIFIED Requirements

### Requirement: Privacy-preserving telemetry
The system SHALL record stage durations, end-to-end first-audio latency when audio is produced, end-to-end duration, selected provider and model versions, active character ID and package version, token usage when available, and terminal status without recording secrets, raw audio content, package paths, prompts, examples, or source-claim text.

#### Scenario: Successful telemetry record
- **WHEN** a turn completes with a loaded character package
- **THEN** one structured summary contains identifiers, character ID and version, provider versions, first-audio and total measurements, usage, and success status

#### Scenario: Error telemetry record
- **WHEN** a turn fails after startup
- **THEN** the summary contains the normalized error type, stage, optional first-audio measurement, and non-sensitive character metadata without API credentials or character content
