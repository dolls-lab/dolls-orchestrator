## Why

The March 7th package now has an isolated nine-case evaluation fixture, but the orchestrator cannot execute it or capture model responses in a repeatable format. A text-only runner is needed now to validate the evaluation boundary offline and to provide the same reproducible input/output record once DeepSeek is explicitly enabled later.

## What Changes

- Add independent loading and validation for character evaluation fixtures without importing `dolls-character` code.
- Add a text-only evaluation runner that composes the active package instruction and examples for each isolated case and invokes the selected LLM adapter without ASR or TTS.
- Add an `evaluate-character` CLI command that writes a stable, versioned JSON report, continues across per-case provider failures, and returns a non-zero status when any case fails.
- Keep rubric criteria unscored in this phase; the report captures them alongside responses for later human or judge-model scoring.
- Document the offline baseline, privacy boundary, and future explicitly enabled DeepSeek workflow.

## Capabilities

### New Capabilities
- `character-evaluation-runner`: Fixture validation, isolated text-only execution, failure handling, and versioned JSON reporting for character evaluations.

### Modified Capabilities
- `character-inspection-cli`: Add a command for selecting a character package, evaluation fixture, LLM profile, and report destination.

## Impact

The change adds an evaluation domain/runner module, one CLI surface, tests, and baseline documentation. It reuses the existing character-package consumer and LLM adapter contracts, adds no dependency, does not access the remote character database, and does not enable DeepSeek networking or require an API key.
