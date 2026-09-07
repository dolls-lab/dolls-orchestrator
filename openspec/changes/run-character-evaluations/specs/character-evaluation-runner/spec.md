## ADDED Requirements

### Requirement: Independent fixture validation
The orchestrator SHALL load evaluation fixtures without importing producer-project code and MUST validate fixture identity, version, language, non-empty cases, unique case IDs, and non-empty category, user, and rubric values before invoking an adapter.

#### Scenario: Compatible March 7th fixture
- **WHEN** the March 7th `0.1.0` fixture is loaded with the March 7th package
- **THEN** all nine ordered cases are available for execution

#### Scenario: Mismatched or malformed fixture
- **WHEN** fixture character identity or language differs from the package, or required case data is malformed
- **THEN** evaluation fails before any LLM request

### Requirement: Isolated text-only execution
The runner SHALL execute every case using only the active character system instruction, package examples, and that case's user message, with a fresh turn context and no ASR, TTS, prior case output, or network activity unless the selected LLM adapter performs an explicitly authorized request.

#### Scenario: Offline evaluation
- **WHEN** the scripted offline LLM is selected
- **THEN** every case completes without an API key, model download, audio operation, or network request

#### Scenario: Cases execute independently
- **WHEN** multiple fixture cases run in order
- **THEN** each LLM input excludes previous case prompts and replies

### Requirement: Versioned unscored report
The runner SHALL produce a report with an explicit contract version, package and fixture identity, provider metadata, summary counts, and ordered per-case prompts, rubrics, replies, usage, elapsed time, status, and null score without including package paths, package prompt text, package examples, or credentials.

#### Scenario: Successful collection
- **WHEN** all cases complete
- **THEN** the report marks every case completed and unscored and preserves source fixture order

#### Scenario: Review report content
- **WHEN** a report is inspected
- **THEN** it contains the evaluation inputs and outputs needed for review but no package-private runtime content or secret configuration

### Requirement: Per-case failure isolation
The runner SHALL normalize an LLM error into the current case result, continue remaining cases, and mark the overall report failed when one or more cases fail.

#### Scenario: One case fails
- **WHEN** an adapter raises during one case
- **THEN** later cases still run and the summary reports both completed and failed counts
