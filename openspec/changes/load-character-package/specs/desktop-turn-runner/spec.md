## MODIFIED Requirements

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
