## Context

`TurnOrchestrator` currently owns one hard-coded character instruction. The sibling `dolls-character` repository now publishes a language-neutral directory contract with a manifest, SHA-256 inventory, prompt, behavior, examples, and compact provenance. The consumer must validate that contract independently because deployed orchestrators receive only a released package directory, not the producer's Python source.

Existing profiles and offline tests must continue to run when no package is configured. DeepSeek remains disabled, so this change can verify exact message construction without making a provider request.

## Goals / Non-Goals

**Goals:**

- Load and validate contract-v1 packages with no new runtime dependency.
- Select a package through environment configuration or per-command override.
- Inject package instructions and examples in a deterministic LLM message order.
- Expose non-sensitive active-character metadata through CLI and telemetry.
- Verify the real March 7th `0.1.0` package across the repository boundary.

**Non-Goals:**

- Building or editing character packages inside the orchestrator.
- Accessing `hksr_database`, loading evaluation fixtures, or performing retrieval.
- Scoring character quality or enabling the DeepSeek network path.
- Automatically discovering sibling repositories in production.

## Decisions

### Independent contract reader

The orchestrator implements its own small standard-library contract-v1 reader. It validates manifest shape, fixed entrypoint names, compatibility, file hashes, behavior limits, examples, and compact provenance before returning an immutable `CharacterPackage`. It does not import `dolls_character` or trust files outside the declared package root.

This duplicates a narrow validation boundary intentionally: producer and consumer tests can catch accidental contract divergence, while deployed code does not depend on the producer repository layout.

### Explicit package selection with fallback

`DOLLS_CHARACTER_PACKAGE_PATH` is optional. `run-turn` and `chat` accept `--character-package` as a higher-priority override. If neither is supplied, the orchestrator uses a named built-in fallback equivalent to the previous instruction. If a path is explicitly supplied but invalid, startup fails; it never silently falls back from a damaged requested package.

### Stable message composition

LLM messages are ordered as: one package system instruction, zero or more package example user/assistant pairs, bounded successful conversation turns, then the current user message. Package examples do not count against the recent-turn limit because they are immutable character configuration.

### Character-aware telemetry

Turn telemetry gains `character_id` and `character_version`. It never includes the package path, prompt, examples, source links, or claim text. Existing telemetry consumers remain compatible because the change only adds fields.

### Inspection CLI

`validate-character PATH` validates an explicit package and returns a compact JSON summary. `character-info` resolves the same optional path/override used by runtime and reports whether the active source is a package or built-in fallback. Neither command reads credentials or starts ASR/LLM/TTS.

## Risks / Trade-offs

- [Producer and consumer validators drift] → Maintain a real cross-repository compatibility smoke test and pin contract version 1 behavior in both specs.
- [Examples make requests larger] → The first package has five short pairs; report their count and revisit token budgeting before adding larger packages.
- [A configured package is edited after startup] → Load and validate once when constructing the orchestrator; keep the immutable in-memory content for the session.
- [Silent fallback hides deployment mistakes] → Fall back only when no path was requested; explicit invalid paths are fatal.

## Migration Plan

1. Deploy with no package path to preserve current behavior.
2. Run `validate-character` and `character-info` against the released March 7th directory.
3. Set `DOLLS_CHARACTER_PACKAGE_PATH` for desktop runs and verify telemetry metadata.
4. Roll back by unsetting the environment variable or removing the CLI override.

## Open Questions

- Later deployments may need a package registry or copied release directory; contract-v1 path loading deliberately does not choose that distribution mechanism.
