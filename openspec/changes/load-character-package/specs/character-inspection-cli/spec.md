## ADDED Requirements

### Requirement: Explicit package validation command
The CLI SHALL provide `validate-character PATH` and output a compact machine-readable summary after validating the complete package.

#### Scenario: Validate a compatible package
- **WHEN** the command receives a valid contract-v1 directory
- **THEN** it exits zero and reports character ID, display name, package version, language, example count, and source type

#### Scenario: Validate an incompatible package
- **WHEN** package validation fails
- **THEN** the command exits non-zero with an actionable error and no prompt, example, or source-claim text

### Requirement: Active character inspection
The CLI SHALL provide `character-info` using the same environment and optional path override resolution as dialogue commands.

#### Scenario: Inspect selected package
- **WHEN** a package path is selected
- **THEN** the command reports its compact metadata and source as `package`

#### Scenario: Inspect fallback
- **WHEN** no package path is selected
- **THEN** the command reports the built-in character identity and source as `builtin`
