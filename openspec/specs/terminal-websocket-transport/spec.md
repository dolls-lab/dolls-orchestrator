# Terminal WebSocket Transport

## Purpose

Define authenticated WebSocket serving, protocol frame routing, injected response delivery, bounded resources, and real localhost verification for terminal protocol draft v0.

## Requirements

### Requirement: Authenticated terminal WebSocket endpoint
The transport SHALL accept WebSocket upgrades only on the configured terminal path when draft-v0 protocol, device, client, and bearer headers validate against the configured server token, and SHALL reject invalid upgrades without exposing credentials.

#### Scenario: Valid localhost upgrade
- **WHEN** a client connects to the terminal path with matching draft-v0 headers
- **THEN** the WebSocket upgrade succeeds and the connection receives a non-secret authenticated identity

#### Scenario: Invalid path or authentication
- **WHEN** the path is unknown or any required header or token is invalid
- **THEN** the upgrade fails with a bounded HTTP response that contains no supplied header value

### Requirement: Protocol frame routing
The transport SHALL route text frames through the draft-v0 JSON codec, route binary frames through the draft-v0 audio gate, and send the canonical server hello after accepting the client hello.

#### Scenario: Hello and uplink frames
- **WHEN** an authenticated connection sends a compatible hello, listen start, bounded binary frames, and listen stop in order
- **THEN** it receives the canonical hello and the turn handler receives the exact ordered binary payloads

#### Scenario: Invalid text frame or control order
- **WHEN** a text frame is malformed, oversized, or carries a control invalid for the current state
- **THEN** the connection closes with a bounded protocol failure and does not invoke a turn handler with invalid data

### Requirement: Injected turn response delivery
The transport SHALL pass immutable non-secret turn input to one injected async handler and SHALL serialize its accepted response as STT, LLM, TTS start, TTS sentence-start, raw audio frames, and TTS stop in canonical order.

#### Scenario: Successful deterministic response
- **WHEN** the injected handler returns transcript, reply, emotion, and bounded audio frames for the active generation
- **THEN** the client receives canonical text events and exact raw audio payloads in order before the session returns to idle

### Requirement: Bounded connection resources
The transport MUST bound each frame and aggregate buffered uplink audio, allow only one active turn per connection, and release connection-owned tasks and buffers on close.

#### Scenario: Aggregate audio exceeds the limit
- **WHEN** otherwise valid audio frames exceed the per-turn aggregate byte limit
- **THEN** the connection rejects the turn before invoking the handler and releases the buffer

#### Scenario: Client disconnects during response work
- **WHEN** the WebSocket closes while the handler is running
- **THEN** response work is cancelled and the connection session is closed

### Requirement: Real offline loopback verification
The project SHALL test the transport through a real localhost TCP/WebSocket server and client without hardware, model loading, microphone access, audio decoding, provider credentials, or external network requests.

#### Scenario: Clean loopback suite
- **WHEN** the terminal transport dependency is installed and the automated suite runs
- **THEN** handshake, text, binary, response, abort, disconnect, and reconnect isolation checks complete using only loopback traffic and synthetic payloads
