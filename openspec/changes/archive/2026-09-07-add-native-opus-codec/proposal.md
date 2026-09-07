## Why

The terminal transport and orchestration bridge currently depend on an abstract audio codec, so the documented raw-Opus wire contract cannot yet be exercised with real audio. A native codec baseline is needed before an offline terminal service can be run end to end without a model API or physical device.

## What Changes

- Add a `libopus`-backed codec implementing the existing terminal audio codec boundary.
- Decode ordered 16 kHz mono Opus uplink packets into signed 16-bit PCM.
- Resample signed 16-bit mono PCM when required and encode ordered 24 kHz mono Opus downlink packets in 60 ms frames.
- Normalize library discovery, invalid format, corrupt packet, and native codec failures into stable orchestrator errors.
- Add native codec unit tests and a real Opus/WebSocket/offline-orchestrator loopback test.
- Document the system `libopus` dependency and raw-packet framing limitations.

## Capabilities

### New Capabilities

- `native-opus-codec`: Native raw-Opus discovery, validation, decoding, resampling, encoding, and error behavior.

### Modified Capabilities

None.

## Impact

- Adds a new codec module and exported codec error/type surfaces.
- Requires a discoverable system installation of `libopus`; no Python wrapper or model API is added.
- Extends tests and operator documentation while preserving the existing WebSocket protocol and orchestration bridge contracts.
