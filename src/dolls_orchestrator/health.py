"""Side-effect-free service readiness aggregation."""

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .character import resolve_character
from .config import Settings
from .domain import AdapterHealth
from .errors import CharacterPackageError
from .errors import OpusCodecError
from .opus_codec import LibOpusCodec
from .profiles import build_profile


@dataclass(frozen=True)
class ServiceHealthReport:
    profile: str
    components: Tuple[AdapterHealth, ...]

    @property
    def ready(self) -> bool:
        return all(component.ready for component in self.components)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "ready" if self.ready else "blocked",
            "profile": self.profile,
            "components": [component.to_dict() for component in self.components],
        }


def _character_health(path: Optional[Path]) -> AdapterHealth:
    try:
        character = resolve_character(path)
    except CharacterPackageError:
        return AdapterHealth(
            "character",
            "character-package",
            "unknown",
            "blocked",
            "package_invalid",
        )
    return AdapterHealth(
        "character",
        character.source,
        character.package_version,
        "ready",
    )


def _terminal_health(settings: Settings) -> Tuple[AdapterHealth, ...]:
    if importlib.util.find_spec("websockets") is None:
        transport = AdapterHealth(
            "terminal_transport",
            "websockets",
            "unknown",
            "blocked",
            "dependency_missing_websockets",
        )
    else:
        transport = AdapterHealth(
            "terminal_transport", "websockets", "installed", "ready"
        )

    try:
        codec = LibOpusCodec(
            str(settings.libopus_path) if settings.libopus_path is not None else None
        )
        opus_version = codec.version
    except OpusCodecError:
        opus = AdapterHealth(
            "terminal_audio_codec",
            "libopus",
            "unknown",
            "blocked",
            "dependency_missing_libopus",
        )
    else:
        opus = AdapterHealth(
            "terminal_audio_codec", "libopus", opus_version, "ready"
        )

    token_ready = bool(settings.terminal_token) and not any(
        character.isspace() for character in settings.terminal_token
    )
    authentication = AdapterHealth(
        "terminal_auth",
        "bearer-token",
        "configured" if token_ready else "unknown",
        "ready" if token_ready else "blocked",
        None if token_ready else "credential_missing",
    )
    return transport, opus, authentication


def check_service_health(
    profile_name: str,
    settings: Settings,
    include_terminal: bool = False,
) -> ServiceHealthReport:
    profile = build_profile(profile_name, settings)
    components = (
        _character_health(settings.character_package_path),
        profile.asr.health(),
        profile.llm.health(),
        profile.tts.health(),
    )
    if include_terminal:
        components += _terminal_health(settings)
    return ServiceHealthReport(
        profile=profile_name,
        components=components,
    )
