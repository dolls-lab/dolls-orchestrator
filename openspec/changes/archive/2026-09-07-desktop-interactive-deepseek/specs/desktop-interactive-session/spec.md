## ADDED Requirements

### Requirement: Push-to-talk recording
The desktop client SHALL start microphone capture only after an explicit user action and SHALL stop on the next explicit action, writing mono 16 kHz 16-bit PCM WAV for the existing ASR contract.

#### Scenario: Successful recording
- **WHEN** the user starts and stops recording and the microphone provides frames
- **THEN** a non-empty supported WAV is passed to the orchestrator

#### Scenario: Empty recording
- **WHEN** recording stops without captured frames
- **THEN** the turn is rejected with an actionable microphone error

#### Scenario: Microphone unavailable
- **WHEN** no input device exists or permission is denied
- **THEN** the client reports how to select or authorize a microphone and remains able to exit

### Requirement: Interactive multi-turn loop
The CLI SHALL offer a `chat` command that displays idle, listening, transcribing/generating/synthesizing, playing, completed, cancelled, and recoverable-error feedback and reuses one session ID across successful turns.

#### Scenario: No-API conversation
- **WHEN** the user selects the local-no-api profile
- **THEN** repeated push-to-talk turns use MLX Whisper, the scripted LLM, and local speech without any API key

#### Scenario: Clean exit
- **WHEN** the user enters the documented quit command while idle
- **THEN** the session exits without starting another recording and removes its temporary audio files

#### Scenario: Recoverable turn failure
- **WHEN** one recording or orchestration turn fails
- **THEN** the error is shown and the interactive loop returns to idle for retry

### Requirement: Automatic reply playback
The client SHALL write each successful reply to a temporary WAV and play it using a configurable local player, waiting for playback to finish before accepting another half-duplex turn.

#### Scenario: Successful playback
- **WHEN** orchestration returns non-empty playable audio
- **THEN** the client displays playing state and invokes the player once with the reply WAV

#### Scenario: Playback disabled
- **WHEN** the user supplies the no-playback option
- **THEN** the WAV and telemetry are produced without invoking a player

### Requirement: Deterministic interactive tests
Recorder, console input, playback, and transport boundaries SHALL be injectable so automated tests can verify session behavior without a microphone, speaker, API key, or network.

#### Scenario: Simulated interactive turn
- **WHEN** tests provide recorded PCM frames, scripted console actions, and a fake player
- **THEN** one complete turn runs and all observable states occur in order without external I/O

