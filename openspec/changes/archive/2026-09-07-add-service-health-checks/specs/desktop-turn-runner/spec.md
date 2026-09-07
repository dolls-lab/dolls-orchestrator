## ADDED Requirements

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
