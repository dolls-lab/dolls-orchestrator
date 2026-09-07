## 1. DeepSeek streaming adapter

- [x] 1.1 Implement guarded request construction and an injectable asynchronous SSE transport
- [x] 1.2 Parse streamed content, completion metadata, usage, and normalized provider errors
- [x] 1.3 Add contract tests for guards, request shape, streaming, malformed data, HTTP errors, and cancellation

## 2. Desktop audio interaction

- [x] 2.1 Define recorder and player protocols plus normalized desktop audio errors
- [x] 2.2 Implement optional sounddevice push-to-talk recording and macOS afplay playback with cleanup
- [x] 2.3 Implement the injectable interactive multi-turn session and chat CLI command

## 3. Verification and documentation

- [x] 3.1 Add deterministic tests for recording, playback, state feedback, retry, clean exit, and no-playback mode
- [x] 3.2 Install optional desktop dependencies and perform available microphone/device and no-API smoke checks
- [x] 3.3 Update setup, privacy, profile, interactive usage, API enablement, and troubleshooting documentation
- [x] 3.4 Run the full test suite, packaging, offline regression, OpenSpec validation, and final review
