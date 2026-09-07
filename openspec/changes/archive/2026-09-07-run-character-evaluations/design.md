## Context

`dolls-character` publishes a contract-v1 runtime package and keeps its March 7th evaluation fixture outside that package. `dolls-orchestrator` can load the package and already has provider-independent streaming LLM adapters, but its existing turn path requires audio and mixes ASR, LLM, and TTS measurements. Evaluation needs a separate text-only boundary so character responses can be collected reproducibly without speech variability or fixture leakage into runtime prompts.

The current fixture contains identity metadata plus nine cases with IDs, categories, user messages, and rubrics. It intentionally contains no reference answers. DeepSeek remains disabled by default and the first baseline must run with the scripted offline adapter.

## Goals / Non-Goals

**Goals:**

- Independently validate the external fixture and its match to the selected package.
- Execute each case in isolation using the package system instruction and examples.
- Capture responses, provider metadata, usage, elapsed time, rubric text, and normalized failures in a stable report schema.
- Preserve a guarded path to the existing DeepSeek adapter without changing its explicit network and API-key checks.
- Make the runner and CLI deterministic under injected test adapters and free of ASR/TTS work.

**Non-Goals:**

- Automatically deciding whether subjective rubric criteria pass.
- Using a judge model, computing a promotion score, or changing the fixture format in `dolls-character`.
- Running audio, querying the remote database, enabling DeepSeek, or storing reports in Git by default.
- Adding cross-case memory; every fixture case is an independent measurement in this phase.

## Decisions

### Independent fixture consumer

The orchestrator validates fixture JSON itself instead of importing producer code. It requires a non-empty evaluation version, matching character ID and language, a non-empty case list, unique IDs, and non-empty category, user, and rubric values. This mirrors the package-consumer boundary and ensures malformed or mismatched data fails before any adapter call.

Alternative: reuse `dolls_character.evaluation`. Rejected because runtime/evaluation deployment would then depend on the producer project and its internal Python API.

### Text-only per-case execution

Each request contains `character.message_prefix()` followed by the case user message. A fresh `TurnContext` and no prior runtime messages are used for every case. This prevents output from one case affecting another and ensures the evaluation fixture is never loaded into the package or system prompt.

Alternative: route through `TurnOrchestrator`. Rejected because synthetic WAV, ASR, sentence splitting, and TTS would add unrelated failure modes and latency.

### Collection before scoring

Report contract version 1 records each rubric verbatim with `score: null`, plus reply and execution metadata. Summary counts distinguish completed, failed, and unscored cases. A later change can add human annotations or an explicitly selected judge without changing how raw responses are collected.

Alternative: keyword scoring. Rejected because the Chinese behavioral rubrics are semantic and keyword heuristics would create misleading pass rates.

### Failure isolation and guarded providers

Fixture/package validation is fail-fast. Once execution starts, a provider failure is normalized into that case result and the runner continues, so one transient failure does not discard the rest of the report. The CLI writes the report atomically after all cases and exits non-zero if any case failed. Selecting `local-voice` reuses `DeepSeekLLMAdapter`; its existing network-enable and key guards remain authoritative.

### Stable report boundary

The JSON uses an explicit report contract version, source metadata, fixture identity, ordered cases, and sorted serialization. It contains evaluation prompts, rubrics, and model replies because those are the artifact under review, but excludes package prompts/examples, package paths, credentials, and transport payloads. Variable runtime measurements mean reports are schema-stable rather than byte-identical.

## Risks / Trade-offs

- [The offline adapter returns the same canned reply for every case] → Label it as plumbing validation only and never calculate a character score from it.
- [A real evaluation report contains user prompts and model replies] → Require an explicit output path and document that reports may contain conversational text.
- [The current multi-turn category has no fixture history] → Execute it as provided and keep scoring unassigned; extend the producer fixture contract in a later coordinated change.
- [Continuing after failures can hide an unhealthy run] → Set a failed summary count and a non-zero CLI exit status while preserving all diagnostics.

## Migration Plan

1. Add and validate the new fixture and report models.
2. Run all nine cases with the offline adapter and inspect the generated report.
3. Keep DeepSeek disabled until the user supplies the key and explicit network flag.
4. Later rerun the identical fixture with `local-voice`, then add a separate scoring workflow.

Rollback is removal of the new CLI command and evaluation module; dialogue paths and character package loading are unchanged.

## Open Questions

- Should the next fixture contract add explicit prior messages for multi-turn cases?
- Should promotion gates use human review, a separate judge model, or both?
