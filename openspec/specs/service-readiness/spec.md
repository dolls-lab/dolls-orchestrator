# Service Readiness

## Purpose

Define stable, side-effect-free readiness reporting across the selected character and service adapters.

## Requirements
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

### Requirement: Optional terminal service readiness
The health command SHALL optionally append stable, bounded readiness components for the WebSocket transport dependency, native Opus codec, and terminal bearer authentication while preserving the existing default readiness report.

#### Scenario: Default adapter readiness
- **WHEN** health is requested without terminal checks
- **THEN** the report contains only the existing character, ASR, LLM, and TTS components in stable order

#### Scenario: Complete terminal readiness
- **WHEN** terminal health is requested with the transport dependency, a usable native codec, and a configured token
- **THEN** the three terminal components are appended in stable order and the overall report is ready only when every base and terminal component is ready

#### Scenario: Missing terminal prerequisite
- **WHEN** terminal health is requested while a terminal dependency or token is absent
- **THEN** the affected component and overall report are blocked without loading models, binding sockets, calling providers, or exposing secret values
