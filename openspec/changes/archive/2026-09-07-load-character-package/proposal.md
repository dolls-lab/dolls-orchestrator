## Why

The orchestrator still embeds a temporary March 7th-style instruction even though `dolls-character` now publishes an integrity-checked `march-7th` package. Loading that package through its public contract makes the first real character configuration versioned, inspectable, and independently replaceable without enabling DeepSeek.

## What Changes

- Add an independent contract-v1 character package consumer that validates manifest compatibility, entrypoints, JSON shapes, and SHA-256 before exposing content.
- Load a configured package from `DOLLS_CHARACTER_PACKAGE_PATH` or a command-line override, while preserving the built-in scripted character as the explicit no-package fallback.
- Compose LLM messages from the package system prompt, examples, bounded completed turns, and current user input in a stable order.
- Record character ID and package version in turn telemetry without recording prompt or example text.
- Add `character-info` and `validate-character` commands for preflight inspection and validation.
- Verify compatibility against the real sibling `dolls-character/packages/march-7th/0.1.0` artifact without making the normal test suite depend on that repository.

## Capabilities

### New Capabilities
- `character-package-consumer`: Safe contract-v1 loading, integrity validation, normalized character content, and built-in fallback behavior.
- `character-inspection-cli`: Character package validation and active-character inspection commands.

### Modified Capabilities
- `turn-orchestration`: Use loaded character instructions and examples for message construction and identify the selected character package in telemetry.
- `desktop-turn-runner`: Accept an optional character package configuration or CLI override for voice turns and interactive chat.

## Impact

- Adds a standard-library-only character loader and typed package errors to `dolls-orchestrator`.
- Changes LLM message construction and extends telemetry output with non-sensitive character metadata.
- Adds optional configuration and CLI flags but preserves existing profile behavior when no package is configured.
- Reads a local published package directory only; it does not import `dolls-character`, query its source tree, access PostgreSQL, or call DeepSeek.
