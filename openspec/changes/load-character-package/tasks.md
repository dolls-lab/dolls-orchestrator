## 1. Character Consumer

- [x] 1.1 Add immutable character package models, built-in fallback metadata, and typed package errors
- [x] 1.2 Implement contract-v1 manifest, safe-entrypoint, JSON-shape, compatibility, and SHA-256 validation
- [x] 1.3 Add deterministic loader tests for valid, malformed, incompatible, unsafe, missing, and tampered packages

## 2. Orchestration Integration

- [x] 2.1 Add optional environment and CLI package-path selection with explicit-invalid-path failure
- [x] 2.2 Compose system instruction, package examples, bounded runtime context, and current input in stable order
- [x] 2.3 Add character ID and version to success and failure telemetry without character content
- [x] 2.4 Add orchestration and configuration tests for package selection, fallback, message order, bounds, and telemetry

## 3. Inspection and Delivery

- [x] 3.1 Add `validate-character` and `character-info` commands with compact JSON output and tests
- [x] 3.2 Verify the real sibling March 7th `0.1.0` package and document setup, fallback, privacy, and commands
- [x] 3.3 Run the full offline suite, CLI and cross-repository smoke checks, packaging, secret scan, and strict OpenSpec validation
