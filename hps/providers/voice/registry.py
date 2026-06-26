from .mock import MockVoiceProvider
from .qwen import QwenVoiceProvider

def get_voice_provider(name):
    name = (name or "mock").lower()
    if name == "mock":
        return MockVoiceProvider()
    if name in ("qwen", "qwen_fal_tts", "qwen_dashscope_tts"):
        return QwenVoiceProvider()
    raise ValueError(f"Unknown voice provider: {name}")
