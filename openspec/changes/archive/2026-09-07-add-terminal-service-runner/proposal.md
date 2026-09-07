## Why

The terminal protocol, WebSocket transport, orchestration bridge, and native Opus codec are individually verified but cannot yet be started as one service. A secure, explicit runner is needed to turn those components into a reproducible offline service without requiring cloud credentials or hardware.

## What Changes

- Add a `serve-terminal` command that assembles the selected adapter profile, character package, orchestrator, native Opus codec, and WebSocket transport.
- Require a bearer token from configuration and keep it out of CLI arguments, status output, exceptions, and object representations.
- Bind to localhost by default and require an explicit LAN opt-in for non-loopback addresses.
- Run terminal-specific readiness checks before binding and expose the same checks through `health --terminal`.
- Close the server and connection-owned work cleanly on shutdown or cancellation.
- Add offline unit and real localhost integration coverage plus operator documentation.

## Capabilities

### New Capabilities

- `terminal-service-runner`: Secure CLI/configuration assembly, startup gating, bind policy, lifecycle, and offline end-to-end behavior for the terminal service.

### Modified Capabilities

- `service-readiness`: Extend the readiness contract with optional terminal transport, native codec, and bearer-token checks.

## Impact

- Adds terminal service configuration fields, runtime assembly code, and a CLI subcommand.
- Extends health reporting without changing the existing default four-component report.
- Uses the existing optional `websockets` extra and system `libopus`; no model API or new Python runtime dependency is introduced.
