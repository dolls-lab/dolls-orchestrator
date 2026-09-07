"""Normalized application errors."""

from typing import Optional


class OrchestratorError(Exception):
    def __init__(self, message: str, stage: str = "orchestration") -> None:
        super().__init__(message)
        self.stage = stage


class InvalidAudioError(OrchestratorError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "asr")


class ProviderConfigurationError(OrchestratorError):
    def __init__(self, message: str, stage: str = "llm") -> None:
        super().__init__(message, stage)


class ProviderUnavailableError(OrchestratorError):
    pass


class StageTimeoutError(OrchestratorError):
    pass


class StaleGenerationError(OrchestratorError):
    def __init__(self, message: str = "turn generation is no longer active") -> None:
        super().__init__(message, "orchestration")


class TurnCancelledError(OrchestratorError):
    def __init__(self, message: str = "turn was cancelled") -> None:
        super().__init__(message, "orchestration")


class DesktopAudioError(OrchestratorError):
    pass


class MicrophoneError(DesktopAudioError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "recording")


class PlaybackError(DesktopAudioError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "playback")
