"""Side-effect-free service readiness aggregation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .character import resolve_character
from .config import Settings
from .domain import AdapterHealth
from .errors import CharacterPackageError
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


def check_service_health(profile_name: str, settings: Settings) -> ServiceHealthReport:
    profile = build_profile(profile_name, settings)
    return ServiceHealthReport(
        profile=profile_name,
        components=(
            _character_health(settings.character_package_path),
            profile.asr.health(),
            profile.llm.health(),
            profile.tts.health(),
        ),
    )
