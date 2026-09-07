## Context

The repository has verified components for draft-v0 protocol parsing, connection state, WebSocket transport, terminal-to-orchestrator bridging, native Opus, adapter profiles, character packages, and readiness reporting. They are intentionally dependency-injected and currently require handwritten assembly. The reference runner must work entirely offline, avoid exposing its bearer token, and remain safe when operators later bind it to a home LAN.

## Goals / Non-Goals

**Goals:**

- Provide one CLI command that assembles and runs the complete terminal service.
- Gate socket binding on character, adapter, WebSocket, native codec, and credential readiness.
- Preserve localhost as the default and make LAN exposure an explicit operator decision.
- Keep the bearer token out of arguments and all output while supporting environment-based deployment.
- Close listening sockets and connection-owned work on signals, cancellation, or normal shutdown.
- Verify the assembled service with offline adapters and real localhost WebSocket/Opus traffic.

**Non-Goals:**

- TLS termination, public-internet deployment, service managers, containers, or firewall automation.
- Automatic token generation, persistence, or secret-store integration.
- Loading models, probing cloud providers, or testing physical terminal hardware during readiness.
- Changing the draft-v0 wire protocol or adding production jitter/retry behavior.

## Decisions

### Add a dedicated terminal service assembly module

`terminal_service.py` will construct the selected adapter profile, character, `TurnOrchestrator`, `LibOpusCodec`, bridge, and transport. Keeping assembly outside the CLI allows real integration tests and future service managers to reuse the same entrypoint. Embedding construction directly in `cli.py` was rejected because it would force tests to invoke an indefinite process.

### Read secrets only from environment-backed settings

`DOLLS_TERMINAL_TOKEN` is optional in general `Settings` so unrelated commands remain usable, but mandatory for terminal readiness and startup. It is stored with `repr=False`; no CLI token flag exists. An optional `DOLLS_LIBOPUS_PATH` supports deterministic deployments without exposing paths in health errors.

### Extend readiness only when terminal checks are requested

The existing four-component health report remains unchanged by default. `health --terminal` appends bounded checks for WebSocket import discovery, loadable `libopus`, and bearer-token presence. The runner calls the same aggregation and rejects blocked startup before invoking the server factory.

### Require explicit LAN opt-in

The default remains `127.0.0.1`. A configured non-loopback host is rejected unless `--allow-lan` is supplied. This prevents accidental exposure while allowing the project's home-LAN use case. The CLI prints only the selected profile and socket address after binding.

### Separate server start from lifecycle waiting

One async function returns a started server for integration and embedding; another owns signal registration, waits for shutdown, and always closes the server in `finally`. Signal handlers only set an event, keeping cleanup on the event-loop thread.

## Risks / Trade-offs

- [Plain WebSocket on a LAN exposes metadata to local observers] → Require explicit LAN opt-in, a bearer token, and documentation that public or untrusted networks require external TLS termination.
- [Environment variables can still be inspected by the local account] → Never echo values and document use of process/service environment controls; secret-store integration remains future work.
- [Readiness can pass before a port bind later fails] → Treat bind errors as startup failures and never claim a listening state before the server factory succeeds.
- [Signal APIs vary across platforms] → Use event-loop signal handlers where supported and retain cancellation/finally cleanup everywhere.

## Migration Plan

1. Install the existing `terminal` extra and system `libopus` dependency.
2. Set a non-empty `DOLLS_TERMINAL_TOKEN` and run `health --terminal`.
3. Start `serve-terminal` on localhost; use `--allow-lan --host <address>` only for an intentionally trusted LAN.
4. Roll back by stopping the command; no persisted data or protocol migration is involved.

## Open Questions

TLS termination and token lifecycle must be decided before any non-trusted-network deployment, but do not block the local/home-LAN baseline.
