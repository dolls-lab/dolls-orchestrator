"""Construction of explicit adapter profiles."""

from dataclasses import dataclass

from .adapters import (
    DeepSeekLLMAdapter,
    MacOSSayTTSAdapter,
    MLXWhisperAdapter,
    OfflineASRAdapter,
    OfflineLLMAdapter,
    ToneTTSAdapter,
)
from .config import Settings
from .domain import ASRAdapter, LLMAdapter, TTSAdapter


@dataclass(frozen=True)
class AdapterProfile:
    asr: ASRAdapter
    llm: LLMAdapter
    tts: TTSAdapter


def build_profile(name: str, settings: Settings) -> AdapterProfile:
    if name == "offline":
        return AdapterProfile(
            asr=OfflineASRAdapter(settings.offline_transcript),
            llm=OfflineLLMAdapter(settings.offline_reply),
            tts=ToneTTSAdapter(settings.output_sample_rate),
        )
    if name == "offline-macos":
        return AdapterProfile(
            asr=OfflineASRAdapter(settings.offline_transcript),
            llm=OfflineLLMAdapter(settings.offline_reply),
            tts=MacOSSayTTSAdapter(
                voice=settings.macos_voice,
                sample_rate=settings.output_sample_rate,
            ),
        )
    if name == "local-no-api":
        return AdapterProfile(
            asr=MLXWhisperAdapter(settings.mlx_whisper_model),
            llm=OfflineLLMAdapter(settings.offline_reply),
            tts=MacOSSayTTSAdapter(
                voice=settings.macos_voice,
                sample_rate=settings.output_sample_rate,
            ),
        )
    if name == "local-voice":
        return AdapterProfile(
            asr=MLXWhisperAdapter(settings.mlx_whisper_model),
            llm=DeepSeekLLMAdapter(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                network_enabled=settings.deepseek_network_enabled,
                max_output_tokens=settings.deepseek_max_output_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
            ),
            tts=MacOSSayTTSAdapter(
                voice=settings.macos_voice,
                sample_rate=settings.output_sample_rate,
            ),
        )
    raise ValueError("unknown adapter profile: %s" % name)
