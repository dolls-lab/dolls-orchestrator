## ADDED Requirements

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
