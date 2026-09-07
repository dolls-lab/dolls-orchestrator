## 1. Fixture Contract

- [x] 1.1 Add immutable evaluation fixture and case models plus typed validation errors
- [x] 1.2 Implement independent JSON validation for identity, language, version, cases, and rubrics
- [x] 1.3 Add fixture tests for valid, malformed, duplicate, and package-mismatched inputs

## 2. Evaluation Execution

- [x] 2.1 Implement isolated text-only case execution over the existing streaming LLM contract
- [x] 2.2 Add versioned report models, per-case failure normalization, ordered serialization, and atomic output
- [x] 2.3 Add deterministic runner tests for message isolation, metadata, failures, summaries, and secret boundaries

## 3. CLI and Delivery

- [x] 3.1 Add `evaluate-character` argument validation, profile selection, report output, and exit semantics
- [x] 3.2 Add CLI tests for offline success, invalid fixtures, guarded DeepSeek, and diagnostic reports
- [x] 3.3 Run the real March 7th nine-case offline baseline and document limitations, privacy, and future DeepSeek usage
- [x] 3.4 Run the complete offline suite, packaging, secret scan, diff checks, and strict OpenSpec validation
