## 1. Project foundation

- [x] 1.1 Add Python packaging, module layout, ignore rules, and centralized validated configuration
- [x] 1.2 Define provider-independent domain models, events, errors, and ASR/LLM/TTS protocols

## 2. Adapter implementations

- [x] 2.1 Implement deterministic offline ASR, streaming LLM, and PCM tone TTS adapters
- [x] 2.2 Implement the disabled-by-default DeepSeek placeholder and injectable MLX Whisper adapter
- [x] 2.3 Implement macOS `say`/`afconvert` speech synthesis with subprocess cleanup and normalized WAV output

## 3. Orchestration and CLI

- [x] 3.1 Implement bounded conversation context, generation lifecycle, Chinese sentence splitting, timeouts, cancellation, recovery, and structured telemetry
- [x] 3.2 Implement adapter profiles and the WAV-to-WAV `run-turn` command with actionable errors

## 4. Verification and documentation

- [x] 4.1 Add unit and contract tests for configuration, adapters, sentence splitting, context, cancellation, and recovery
- [x] 4.2 Add an offline end-to-end test that validates the generated WAV and telemetry
- [x] 4.3 Document setup, configuration, privacy behavior, CLI usage, profile limitations, and future API enablement
- [x] 4.4 Run the complete offline test suite, CLI smoke test, OpenSpec validation, and packaging checks
