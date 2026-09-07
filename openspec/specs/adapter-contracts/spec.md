# Adapter Contracts

## Purpose

Define provider-independent boundaries for speech recognition, language generation, speech synthesis, and cancellation.

## Requirements

### Requirement: Provider-independent speech recognition
The system SHALL expose an asynchronous ASR adapter contract that accepts an audio input and turn context and returns recognized text, language, audio duration, confidence when available, provider identity, model version, and elapsed time.

#### Scenario: Successful transcription
- **WHEN** a configured ASR adapter receives supported audio
- **THEN** it returns a normalized result without exposing provider SDK types to the orchestrator

#### Scenario: Recognition failure
- **WHEN** the ASR provider rejects, times out, or cannot understand the audio
- **THEN** the adapter raises a normalized typed error that identifies the failed stage

### Requirement: Incremental language-model output
The system SHALL expose an asynchronous LLM adapter contract that yields normalized text-delta and optional reply-metadata events and ends with provider, model, usage, and timing information.

#### Scenario: Streaming reply
- **WHEN** an LLM adapter produces a reply incrementally
- **THEN** the orchestrator receives ordered text deltas independent of the provider protocol

#### Scenario: Unconfigured DeepSeek provider
- **WHEN** the DeepSeek provider is selected without explicit network enablement or an API key
- **THEN** it fails before any network request with an actionable configuration error

### Requirement: Incremental speech synthesis output
The system SHALL expose an asynchronous TTS adapter contract that accepts normalized synthesis requests and yields ordered audio chunks with format and version metadata.

#### Scenario: Successful synthesis
- **WHEN** a TTS adapter receives a non-empty sentence
- **THEN** it produces audio chunks whose declared format matches their payload

### Requirement: Shared cancellation semantics
All adapter operations MUST honor cancellation of their owning turn and MUST NOT publish usable output after that turn becomes stale.

#### Scenario: Adapter completes after cancellation
- **WHEN** an adapter operation completes after its generation has been cancelled or superseded
- **THEN** its result is discarded by the orchestration boundary

### Requirement: Side-effect-free adapter health
Each built-in ASR, LLM, and TTS adapter SHALL expose a normalized synchronous readiness check that reports its stage, provider, model, status, and bounded reason without invoking its primary operation or external I/O.

#### Scenario: Offline adapter health
- **WHEN** a deterministic offline adapter is checked
- **THEN** it reports ready without reading audio or producing output

#### Scenario: Optional dependency missing
- **WHEN** an adapter's required local import or executable cannot be discovered
- **THEN** it reports blocked with a dependency-missing or command-missing reason

#### Scenario: Guarded provider configuration
- **WHEN** DeepSeek is checked while network access is disabled or its key is absent
- **THEN** it reports the corresponding bounded reason without calling the transport
