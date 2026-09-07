## ADDED Requirements

### Requirement: Character evaluation command
The CLI SHALL provide `evaluate-character` with required character-package, evaluation-fixture, and output paths plus an explicit LLM profile selection, and SHALL write a stable JSON report after execution.

#### Scenario: Offline command
- **WHEN** the command selects the offline profile with compatible March 7th inputs
- **THEN** it writes a nine-case report and exits zero without enabling network access

#### Scenario: Invalid fixture
- **WHEN** the command receives a malformed or package-mismatched fixture
- **THEN** it exits non-zero without invoking the LLM or writing a success report

#### Scenario: Case execution failure
- **WHEN** one or more cases fail after execution starts
- **THEN** the command writes the complete diagnostic report and exits non-zero
