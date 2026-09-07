"""Built-in adapter implementations."""

from .deepseek import DeepSeekLLMAdapter, DeepSeekPlaceholderAdapter
from .macos_tts import MacOSSayTTSAdapter
from .mlx_whisper import MLXWhisperAdapter
from .offline import OfflineASRAdapter, OfflineLLMAdapter, ToneTTSAdapter

__all__ = [
    "DeepSeekPlaceholderAdapter",
    "DeepSeekLLMAdapter",
    "MacOSSayTTSAdapter",
    "MLXWhisperAdapter",
    "OfflineASRAdapter",
    "OfflineLLMAdapter",
    "ToneTTSAdapter",
]
