# Character Package Consumer

## Purpose

Define independent, safe, and deterministic loading of contract-v1 character packages for orchestration.

## Requirements

### Requirement: Independent contract-v1 loading
The orchestrator SHALL load a character package from a local directory without importing producer-project code and MUST validate contract version, character identity, language, compatibility, fixed entrypoints, JSON shapes, and every declared SHA-256 before using its content.

#### Scenario: Valid March 7th package
- **WHEN** the consumer loads the released `march-7th` version `0.1.0` package
- **THEN** it returns normalized immutable prompt, behavior, examples, source summary, character ID, language, and version

#### Scenario: Tampered package
- **WHEN** an entrypoint is missing or its content no longer matches the manifest
- **THEN** startup fails with an actionable character-package error before an adapter is invoked

### Requirement: Safe package path boundary
The loader MUST use the contract-v1 entrypoint names and MUST NOT follow an absolute or parent-traversing entrypoint outside the package root.

#### Scenario: Unsafe entrypoint path
- **WHEN** a manifest names an absolute path or a path containing a parent traversal
- **THEN** package validation fails without reading that target

### Requirement: Explicit built-in fallback
The orchestrator SHALL use its built-in character instruction only when no package path is configured or supplied and SHALL NOT silently fall back when an explicit package fails validation.

#### Scenario: No package selected
- **WHEN** a turn starts without an environment path or command-line override
- **THEN** it uses the identified built-in fallback and retains existing offline behavior

#### Scenario: Explicit invalid package
- **WHEN** the user selects a missing, incompatible, malformed, or tampered package
- **THEN** startup terminates with a configuration error rather than using the fallback

### Requirement: Compact package data boundary
The consumer SHALL load only runtime package entrypoints and SHALL NOT access the producer source tree, evaluation fixtures, remote database, or source evidence corpus.

#### Scenario: Load published package
- **WHEN** a valid package is selected
- **THEN** all character runtime content is obtained from its five contract files with no network activity
