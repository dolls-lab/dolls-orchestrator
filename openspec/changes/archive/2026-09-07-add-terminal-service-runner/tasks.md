## 1. Configuration and readiness

- [x] 1.1 Add validated terminal host, port, bearer token, and optional libopus path settings with secret-safe representation.
- [x] 1.2 Extend health aggregation and CLI output with opt-in terminal transport, codec, and authentication checks.

## 2. Service assembly and lifecycle

- [x] 2.1 Implement reusable offline-capable terminal service assembly and readiness-gated startup.
- [x] 2.2 Enforce localhost-by-default and explicit LAN opt-in before binding.
- [x] 2.3 Implement event, cancellation, and signal-driven graceful shutdown.
- [x] 2.4 Add the `serve-terminal` CLI command without a token argument.

## 3. Verification and documentation

- [x] 3.1 Add configuration, readiness, bind-policy, lifecycle, and CLI unit tests.
- [x] 3.2 Add a real localhost raw-Opus/WebSocket test through the assembled offline service.
- [x] 3.3 Document secure startup, terminal health, LAN caveats, and shutdown behavior.
- [x] 3.4 Run the full suite, compile/package checks, strict OpenSpec validation, secret scan, and diff checks.
