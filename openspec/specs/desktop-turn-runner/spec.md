# Desktop Turn Runner

## Purpose

Define the command-line voice-turn runner, adapter profiles, configuration, and offline verification contract.

## Requirements

### Requirement: WAV-to-WAV command-line turn
The desktop runner SHALL accept a readable WAV input path, execute one voice turn using a named adapter profile, and write a playable WAV output to the requested path.

#### Scenario: Offline deterministic run
- **WHEN** the user runs a turn with the offline profile and no API credentials
- **THEN** the command succeeds, prints recognized and reply text plus telemetry, and writes a valid WAV file

#### Scenario: Invalid input path
- **WHEN** the input WAV does not exist or is not a supported WAV file
- **THEN** the command exits non-zero with an actionable error and does not report success

### Requirement: Explicit provider profiles
The runner SHALL support an offline profile for deterministic verification, a local-no-api profile that wires MLX Whisper to a fixed LLM and macOS speech synthesis, and a local-voice profile that wires MLX Whisper, DeepSeek, and macOS speech synthesis through the same contracts.

#### Scenario: Select offline profile
- **WHEN** the offline profile is selected
- **THEN** no network request or downloaded model is required

#### Scenario: Select local-voice profile without API access
- **WHEN** the local-voice profile reaches the disabled DeepSeek adapter
- **THEN** it terminates with a configuration error before any network activity

#### Scenario: Select local-no-api profile
- **WHEN** MLX Whisper and its configured model are available and the local-no-api profile is selected
- **THEN** the runner performs real local transcription and local speech synthesis without an API key

### Requirement: Central validated configuration
The application SHALL load non-secret defaults and environment overrides, including an optional local character package path, into one validated configuration object, and secrets SHALL only be accepted through environment variables.

#### Scenario: Missing optional API key
- **WHEN** no DeepSeek API key is present and the offline profile is selected
- **THEN** configuration succeeds without inventing or persisting a key

#### Scenario: No character package path
- **WHEN** `DOLLS_CHARACTER_PACKAGE_PATH` is absent
- **THEN** configuration succeeds and selects the built-in character fallback

#### Scenario: Character package path override
- **WHEN** a dialogue command receives `--character-package`
- **THEN** that local path takes precedence over the environment path and is validated before the turn or session starts

#### Scenario: Invalid configuration value
- **WHEN** a timeout, context limit, output-token limit, or explicitly selected character package is invalid
- **THEN** startup fails with a clear validation error

### Requirement: Automated offline verification
The project SHALL provide unit, contract, and end-to-end tests that run without network access, API keys, or downloaded speech models.

#### Scenario: Clean checkout verification
- **WHEN** the documented test command is executed on a supported Python installation
- **THEN** all offline tests complete deterministically

### Requirement: Profile health command
The CLI SHALL provide `health` with profile and optional character-package selection and SHALL print one stable JSON readiness report without running a voice turn.

#### Scenario: Ready profile
- **WHEN** every selected component passes structural preflight
- **THEN** the command exits zero and reports overall ready

#### Scenario: Blocked profile
- **WHEN** one or more components are blocked
- **THEN** the command exits one after reporting all component results

#### Scenario: Invalid ordinary configuration
- **WHEN** environment configuration cannot be parsed
- **THEN** the command exits two with the existing configuration error semantics
