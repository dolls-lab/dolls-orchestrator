## ADDED Requirements

### Requirement: Stable service readiness report
The system SHALL report the selected character, ASR, LLM, and TTS components in stable order with provider/model identity, ready or blocked status, and a bounded reason code, and SHALL mark the overall service ready only when every component is ready.

#### Scenario: Fully offline profile
- **WHEN** the built-in character and offline profile are checked
- **THEN** all four components and the overall report are ready

#### Scenario: Partially blocked profile
- **WHEN** one component lacks a prerequisite
- **THEN** that component and the overall report are blocked while all other component results remain present

### Requirement: Character readiness boundary
The readiness report SHALL validate an explicitly selected character package or identify the built-in fallback without exposing package paths, prompts, examples, source claims, or validation exception details.

#### Scenario: Invalid selected package
- **WHEN** an explicit package is missing, malformed, incompatible, or tampered
- **THEN** the character component is blocked with a generic package-invalid reason and adapter checks still run

### Requirement: Side-effect-free preflight
Readiness checks MUST NOT perform transcription, synthesis, playback, microphone access, model download/load, remote provider requests, or other primary adapter operations.

#### Scenario: DeepSeek is disabled
- **WHEN** local-voice readiness is checked without network enablement
- **THEN** the LLM component reports network-disabled and no transport is invoked

#### Scenario: Local dependencies are inspected
- **WHEN** MLX or macOS adapter readiness is checked
- **THEN** only import or executable discovery occurs

### Requirement: Secret-safe health data
Health results and errors MUST NOT contain credentials, authorization headers, secret values, character content, or raw environment values.

#### Scenario: Key is missing or present
- **WHEN** DeepSeek readiness is inspected
- **THEN** output exposes only a bounded credential-missing reason or ready status, never the key
