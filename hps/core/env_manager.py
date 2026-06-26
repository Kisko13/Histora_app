from pathlib import Path
from typing import Dict

DEFAULTS = {
    "TTS_PROVIDER": "mock",
    "ALLOW_PAID_GENERATION": "false",
    "MAX_BUILD_COST_USD": "0.50",
    "ESTIMATED_QWEN_COST_PER_1K_CHARS": "0.0115",
    "ESTIMATED_QWEN_VOICE_DESIGN_COST_USD": "0.20",
    "DASHSCOPE_API_KEY": "",
    "QWEN_WORKSPACE_ID": "",
    "QWEN_REGION": "singapore",
    "QWEN_TTS_MODEL": "qwen3-tts-flash",
    "QWEN_TTS_INSTRUCT_MODEL": "qwen3-tts-instruct-flash",
    "QWEN_VOICE_DESIGN_MODEL": "qwen-voice-design",
    "QWEN_VOICE_DESIGN_TARGET_MODEL": "qwen3-tts-vd-2026-01-26",
    "QWEN_DEFAULT_VOICE": "Cherry",
    "IMAGE_PROVIDER": "mock",
    "ALLOW_PAID_IMAGE_GENERATION": "false",
    "MAX_IMAGE_BUILD_COST_USD": "0.50",
    "OPENAI_API_KEY": "",
    "OPENAI_IMAGE_MODEL": "gpt-image-1",
    "OPENAI_IMAGE_SIZE": "1536x1024",
    "OPENAI_IMAGE_QUALITY": "medium",
    "ESTIMATED_OPENAI_IMAGE_COST_USD": "0.04",
}

ORDER = [
    "TTS_PROVIDER", "ALLOW_PAID_GENERATION", "MAX_BUILD_COST_USD",
    "ESTIMATED_QWEN_COST_PER_1K_CHARS", "ESTIMATED_QWEN_VOICE_DESIGN_COST_USD",
    "DASHSCOPE_API_KEY", "QWEN_WORKSPACE_ID", "QWEN_REGION", "QWEN_TTS_MODEL",
    "QWEN_TTS_INSTRUCT_MODEL", "QWEN_VOICE_DESIGN_MODEL", "QWEN_VOICE_DESIGN_TARGET_MODEL",
    "QWEN_DEFAULT_VOICE", "IMAGE_PROVIDER", "ALLOW_PAID_IMAGE_GENERATION",
    "MAX_IMAGE_BUILD_COST_USD", "OPENAI_API_KEY", "OPENAI_IMAGE_MODEL",
    "OPENAI_IMAGE_SIZE", "OPENAI_IMAGE_QUALITY", "ESTIMATED_OPENAI_IMAGE_COST_USD"
]

def read_env(app_root: Path) -> Dict[str, str]:
    path = Path(app_root) / ".env"
    vals = dict(DEFAULTS)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals

def write_env(app_root: Path, values: Dict[str, str]) -> Path:
    vals = dict(DEFAULTS)
    vals.update({k: str(v) for k, v in values.items() if k in DEFAULTS})
    path = Path(app_root) / ".env"
    lines = []
    for k in ORDER:
        if k == "ALLOW_PAID_GENERATION":
            lines.append("")
            lines.append("# Voice Safety")
        if k == "DASHSCOPE_API_KEY":
            lines.append("")
            lines.append("# Qwen / Alibaba Cloud Model Studio")
        if k == "IMAGE_PROVIDER":
            lines.append("")
            lines.append("# Image Provider")
        lines.append(f"{k}={vals[k]}")
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return path
