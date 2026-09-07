## ADDED Requirements

### Requirement: Evidence-backed automatic completion matrix
The project SHALL maintain a current status document that maps each completed no-API/no-hardware MVP capability to its executable specification, automated verification, or operator documentation.

#### Scenario: Automatic plan audit
- **WHEN** maintainers inspect the current project status
- **THEN** they can distinguish implemented and verified automatic capabilities from historical phase plans

### Requirement: Explicit external validation boundary
The status document MUST list API credentials, physical terminal testing, real network/playback timing, character quality review, and user-selected thresholds as external work until direct evidence exists, and MUST NOT infer completion from mocks or offline fixtures.

#### Scenario: Offline suite passes
- **WHEN** all offline and localhost automated tests pass without API or hardware
- **THEN** the automatic plan is complete while API, device, and product-quality acceptance remain explicitly pending

### Requirement: Current documentation links
Earlier phase documents SHALL replace obsolete next-step claims with links to completed successor baselines while preserving their original scoped results.

#### Scenario: Reader follows an old phase document
- **WHEN** a previously planned successor has been implemented
- **THEN** the document points to the current implementation or status matrix instead of describing that successor as future work
