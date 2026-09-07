## ADDED Requirements

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
