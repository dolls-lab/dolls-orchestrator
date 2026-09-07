## ADDED Requirements

### Requirement: Native Opus dependency discovery
The system SHALL load `libopus` from an explicit library path or a supported host discovery location and SHALL fail with a normalized codec error when no usable library is available.

#### Scenario: Explicit library is available
- **WHEN** an operator constructs the codec with a valid `libopus` path
- **THEN** the system loads that library and reports its native version

#### Scenario: Library is unavailable
- **WHEN** no usable explicit or discovered `libopus` library exists
- **THEN** codec construction fails with a secret-safe `terminal_audio_codec` error

### Requirement: Ordered uplink decoding
The system SHALL decode each ordered raw-Opus uplink packet using one operation-scoped decoder and SHALL return non-empty signed 16-bit mono PCM at the negotiated sample rate.

#### Scenario: Valid 16 kHz uplink packets
- **WHEN** the codec receives ordered 16 kHz mono Opus packets negotiated with 60 ms framing
- **THEN** it returns aligned `pcm_s16le` mono audio at 16 kHz

#### Scenario: Corrupt uplink packet
- **WHEN** an uplink packet cannot be decoded by `libopus`
- **THEN** the codec fails with a normalized `terminal_audio_codec` error without exposing packet contents

### Requirement: Fixed-frame downlink encoding
The system SHALL encode signed 16-bit mono PCM into ordered raw-Opus packets at the negotiated target rate and frame duration, padding only the final incomplete PCM frame with silence.

#### Scenario: Exact 24 kHz downlink frames
- **WHEN** the codec receives 24 kHz mono PCM whose duration is an exact multiple of 60 ms
- **THEN** it emits one non-empty raw-Opus packet for each 60 ms input frame

#### Scenario: Incomplete final frame
- **WHEN** the final PCM segment is shorter than the negotiated 60 ms frame
- **THEN** the codec pads that segment with silence and emits one final packet

### Requirement: Deterministic PCM resampling
The system SHALL resample aligned signed 16-bit mono PCM when the orchestrator source sample rate differs from the negotiated Opus target sample rate.

#### Scenario: Resample 16 kHz PCM to 24 kHz Opus
- **WHEN** the codec is asked to encode 16 kHz mono PCM for the 24 kHz downlink
- **THEN** decoded output duration remains within one target sample of the padded frame duration

### Requirement: Codec input validation
The system SHALL reject empty audio, unsupported formats, unsupported sample rates or channels, invalid frame durations, oversized packets, and incomplete PCM samples before unsafe native processing.

#### Scenario: Unsupported target parameters
- **WHEN** encoding is requested with stereo or a non-Opus target
- **THEN** the codec fails with a normalized `terminal_audio_codec` error

#### Scenario: Incomplete PCM sample
- **WHEN** the PCM byte count is not aligned to signed 16-bit mono samples
- **THEN** the codec rejects the input without invoking the native encoder

### Requirement: Real offline transport loopback
The system SHALL support a localhost WebSocket turn using real Opus packets, the terminal audio bridge, and offline orchestration adapters without cloud credentials or hardware.

#### Scenario: Complete real-codec turn
- **WHEN** a valid Opus uplink turn is sent to the localhost terminal transport backed by offline adapters
- **THEN** the client receives canonical STT, LLM, and TTS messages plus decodable non-silent Opus downlink packets
