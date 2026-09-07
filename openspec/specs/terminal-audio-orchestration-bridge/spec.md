# Terminal Audio Orchestration Bridge

## Purpose

Define codec-neutral terminal audio conversion, temporary WAV adaptation, connection-scoped orchestration, response mapping, cancellation, and offline end-to-end verification.

## Requirements

### Requirement: Replaceable terminal audio codec
The bridge SHALL depend on an asynchronous codec contract that decodes ordered draft-v0 uplink frames into normalized PCM and encodes orchestrator PCM into ordered draft-v0 downlink frames without exposing codec-specific types to the transport or orchestrator.

#### Scenario: Decode canonical uplink
- **WHEN** a terminal turn contains ordered 16 kHz mono Opus frames
- **THEN** the codec receives those exact frames and canonical uplink parameters and returns PCM with explicit format metadata

#### Scenario: Encode canonical downlink
- **WHEN** orchestration returns non-empty PCM and its source format
- **THEN** the codec receives that data plus canonical 24 kHz mono Opus target parameters and returns ordered opaque frames

### Requirement: Validated temporary WAV adaptation
The bridge MUST require non-empty 16 kHz mono signed-16 decoded PCM, write it to a private per-turn temporary WAV for the orchestrator, and delete the temporary directory on success, failure, or cancellation.

#### Scenario: Valid decoded audio
- **WHEN** the codec returns valid canonical uplink PCM
- **THEN** the orchestrator receives a readable WAV only for the duration of that turn

#### Scenario: Invalid decoded audio
- **WHEN** decoded PCM is empty or its sample rate, channels, width, or encoding is incompatible
- **THEN** the bridge raises a bounded audio-bridge error before invoking the orchestrator

### Requirement: Connection-scoped orchestration mapping
The bridge SHALL run orchestration under the transport session ID and map the completed transcript, reply, a bounded default emotion, and validated encoded audio frames into one terminal turn response.

#### Scenario: Successful offline bridge turn
- **WHEN** decoding, offline orchestration, and encoding succeed
- **THEN** the terminal response contains the orchestrator transcript and reply, neutral emotion, and exact encoded frame order

#### Scenario: Invalid encoded response
- **WHEN** the codec returns no downlink frames or an invalid frame
- **THEN** the bridge raises a bounded audio-bridge error and does not return a partial terminal response

### Requirement: Cancellation preservation
The bridge MUST preserve transport task cancellation across normalized orchestrator cancellation and MUST NOT return a terminal response for a cancelled generation.

#### Scenario: Abort reaches active orchestration
- **WHEN** the transport cancels the bridge while orchestration is running
- **THEN** active orchestration is cancelled, temporary data is removed, and cancellation returns to the transport without an internal-failure response

### Requirement: Offline end-to-end bridge verification
The project SHALL verify the bridge through the real localhost WebSocket transport with deterministic adapters and a synthetic codec, without real Opus processing, hardware, microphone access, model loading, credentials, or external requests.

#### Scenario: Synthetic terminal voice turn
- **WHEN** a loopback client sends synthetic uplink frames through a bridge backed by the offline profile
- **THEN** it receives canonical transcript, reply, TTS lifecycle, and synthetic downlink frames produced through the orchestrator
