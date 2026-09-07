## ADDED Requirements

### Requirement: Sequential continuous-turn benchmark
The benchmark SHALL execute a positive configured number of voice turns sequentially through one orchestrator and one bounded conversation session using a readable WAV input.

#### Scenario: Offline repeated turns
- **WHEN** an operator runs five turns with the offline profile and a valid WAV
- **THEN** all five turns execute in order without network, model loading, microphone, playback, or retained generated audio

### Requirement: Isolated failure and recovery accounting
The benchmark SHALL record a normalized failed turn, continue with the next turn, and count a recovery opportunity as recovered only when the immediately following attempted turn completes.

#### Scenario: Failure followed by success
- **WHEN** one turn fails and the next turn completes
- **THEN** both records remain ordered and the summary counts one recovery opportunity and one recovery

#### Scenario: Benchmark cancellation
- **WHEN** the benchmark task is cancelled during a turn
- **THEN** cancellation propagates and no partial final report is claimed

### Requirement: Deterministic aggregate metrics
The benchmark SHALL calculate completed and failed counts, success rate, and nearest-rank P50/P95 first-audio and total latency over successful turns with available measurements.

#### Scenario: Successful measurement set
- **WHEN** successful turns contain ordered or unordered latency measurements
- **THEN** the report contains deterministic nearest-rank P50 and P95 values and their sample counts

#### Scenario: No successful first-audio measurement
- **WHEN** no successful turn contains first-audio latency
- **THEN** the corresponding sample count is zero and percentile values are null

### Requirement: Versioned privacy-preserving report
The benchmark SHALL atomically write a versioned JSON report containing profile, non-sensitive character/provider/model identities, aggregate metrics, and normalized ordered turn diagnostics without transcripts, replies, audio, input paths, prompts, examples, credentials, or exception messages.

#### Scenario: Report inspection
- **WHEN** a benchmark with a configured character and credential-bearing settings completes
- **THEN** the report supports aggregate and per-turn diagnosis without containing character content, input content, paths, or secret values

### Requirement: Benchmark CLI
The CLI SHALL accept input, output, profile, positive turn count, optional session ID, and optional character package, write the report after all non-cancelled attempts, print a compact summary, and exit nonzero when any turn failed.

#### Scenario: Successful offline command
- **WHEN** `benchmark-turns` runs offline with a valid WAV and writable output
- **THEN** it writes a completed report and exits zero

#### Scenario: Invalid count or output
- **WHEN** the turn count is non-positive or the report cannot be written
- **THEN** the command exits with a bounded configuration or benchmark error
