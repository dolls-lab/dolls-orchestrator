# DeepSeek Streaming

## Purpose

Define guarded DeepSeek Chat Completions streaming, normalization, error handling, and cancellation.

## Requirements

### Requirement: Explicitly guarded DeepSeek requests
The DeepSeek adapter MUST reject execution before opening a connection unless network access is explicitly enabled and a non-empty API key is supplied through the environment.

#### Scenario: Network disabled
- **WHEN** the adapter is invoked while the network-enable setting is false
- **THEN** it raises a typed configuration error and does not call its transport

#### Scenario: Key missing
- **WHEN** network access is enabled but no API key is configured
- **THEN** it raises a typed configuration error and does not call its transport

### Requirement: Non-thinking streaming request
The adapter SHALL send an OpenAI-compatible Chat Completions request to the configured HTTPS base URL using the configured model, full bounded message history, `stream=true`, the configured output limit, and `thinking.type=disabled`.

#### Scenario: Authorized request construction
- **WHEN** the adapter is explicitly enabled with a key
- **THEN** the transport receives the expected endpoint, bearer authorization header, messages, model, stream flag, output limit, and disabled-thinking setting

### Requirement: Normalized SSE output
The adapter SHALL parse data-only SSE records into ordered text-delta events and one completion event carrying model, usage, finish reason, and elapsed time, while ignoring keep-alives and the terminal `[DONE]` marker.

#### Scenario: Successful stream
- **WHEN** the service returns multiple content deltas followed by usage and completion
- **THEN** the adapter emits the content in source order and one normalized completion event

#### Scenario: Malformed event
- **WHEN** a non-empty SSE data record is invalid JSON or lacks a supported response shape
- **THEN** the adapter raises a typed provider error without committing a partial reply

### Requirement: HTTP and provider error normalization
The adapter SHALL map authentication, rate-limit, timeout, server, insufficient-resource, and other provider failures to actionable normalized errors without including the API key.

#### Scenario: Authentication failure
- **WHEN** the provider returns HTTP 401 or 403
- **THEN** the adapter raises an authentication configuration error with no secret value

#### Scenario: Rate limit or server failure
- **WHEN** the provider returns HTTP 429 or a 5xx response
- **THEN** the adapter raises a retryable provider-unavailable error containing the status category

### Requirement: Stream cancellation
The transport MUST close the active response and stop its worker when the owning async stream is cancelled.

#### Scenario: Turn cancellation during SSE
- **WHEN** the orchestrator cancels a turn while SSE records are arriving
- **THEN** the transport stops delivery and releases its response resources
