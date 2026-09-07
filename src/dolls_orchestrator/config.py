"""Central, environment-backed application configuration."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping, Optional


class ConfigurationError(ValueError):
    """Raised when application configuration is invalid."""


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError("%s must be an integer" % name) from exc
    if value <= 0:
        raise ConfigurationError("%s must be greater than zero" % name)
    return value


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError("%s must be a number" % name) from exc
    if value <= 0:
        raise ConfigurationError("%s must be greater than zero" % name)
    return value


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError("%s must be a boolean" % name)


@dataclass(frozen=True)
class Settings:
    profile: str = "offline"
    context_turns: int = 6
    sentence_max_chars: int = 80
    asr_timeout_seconds: float = 60.0
    llm_timeout_seconds: float = 30.0
    tts_timeout_seconds: float = 30.0
    output_sample_rate: int = 24000
    offline_transcript: str = "今天过得怎么样？"
    offline_reply: str = "今天过得不错呀！能和你聊天，我就更开心啦。"
    deepseek_api_key: Optional[str] = field(default=None, repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_network_enabled: bool = False
    deepseek_max_output_tokens: int = 256
    mlx_whisper_model: str = "mlx-community/whisper-small-mlx"
    macos_voice: str = "Tingting"
    character_package_path: Optional[Path] = None

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "Settings":
        env = os.environ if environ is None else environ
        profile = env.get("DOLLS_PROFILE", "offline").strip()
        if profile not in {"offline", "offline-macos", "local-no-api", "local-voice"}:
            raise ConfigurationError(
                "DOLLS_PROFILE must be offline, offline-macos, local-no-api, or local-voice"
            )
        base_url = env.get("DOLLS_LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if not base_url.startswith("https://"):
            raise ConfigurationError("DOLLS_LLM_BASE_URL must use https")
        model = env.get("DOLLS_LLM_MODEL", "deepseek-v4-flash").strip()
        if not model:
            raise ConfigurationError("DOLLS_LLM_MODEL must not be empty")
        return cls(
            profile=profile,
            context_turns=_positive_int(env, "DOLLS_CONTEXT_TURNS", 6),
            sentence_max_chars=_positive_int(env, "DOLLS_SENTENCE_MAX_CHARS", 80),
            asr_timeout_seconds=_positive_float(env, "DOLLS_ASR_TIMEOUT_SECONDS", 60.0),
            llm_timeout_seconds=_positive_float(env, "DOLLS_LLM_TIMEOUT_SECONDS", 30.0),
            tts_timeout_seconds=_positive_float(env, "DOLLS_TTS_TIMEOUT_SECONDS", 30.0),
            output_sample_rate=_positive_int(env, "DOLLS_OUTPUT_SAMPLE_RATE", 24000),
            offline_transcript=env.get(
                "DOLLS_OFFLINE_TRANSCRIPT", "今天过得怎么样？"
            ),
            offline_reply=env.get(
                "DOLLS_OFFLINE_REPLY", "今天过得不错呀！能和你聊天，我就更开心啦。"
            ),
            deepseek_api_key=env.get("DEEPSEEK_API_KEY") or None,
            deepseek_base_url=base_url,
            deepseek_model=model,
            deepseek_network_enabled=_bool(env, "DOLLS_DEEPSEEK_NETWORK_ENABLED", False),
            deepseek_max_output_tokens=_positive_int(
                env, "DOLLS_LLM_MAX_OUTPUT_TOKENS", 256
            ),
            mlx_whisper_model=env.get(
                "DOLLS_MLX_WHISPER_MODEL", "mlx-community/whisper-small-mlx"
            ),
            macos_voice=env.get("DOLLS_MACOS_VOICE", "Tingting"),
            character_package_path=(
                Path(env["DOLLS_CHARACTER_PACKAGE_PATH"].strip()).expanduser()
                if env.get("DOLLS_CHARACTER_PACKAGE_PATH", "").strip()
                else None
            ),
        )
