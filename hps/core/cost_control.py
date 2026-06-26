import os
from dotenv import load_dotenv
load_dotenv()

def paid_generation_allowed():
    return os.getenv("ALLOW_PAID_GENERATION", "false").lower() == "true"

def max_build_cost_usd():
    try:
        return float(os.getenv("MAX_BUILD_COST_USD", "1.00"))
    except Exception:
        return 1.0

def qwen_cost_per_1k_chars():
    try:
        return float(os.getenv("ESTIMATED_QWEN_COST_PER_1K_CHARS", "0.015"))
    except Exception:
        return 0.015

def qwen_voice_design_cost():
    try:
        return float(os.getenv("ESTIMATED_QWEN_VOICE_DESIGN_COST_USD", "0.20"))
    except Exception:
        return 0.20

def estimate_voice_cost(char_count, provider):
    if provider == "mock":
        return 0.0
    return (char_count / 1000.0) * qwen_cost_per_1k_chars()

def cost_guard(db, mode, provider):
    chars, blocks = db.estimate_chars_for_mode(mode)
    estimated = estimate_voice_cost(chars, provider)
    allowed = paid_generation_allowed() or provider == "mock"
    max_cost = max_build_cost_usd()
    return {
        "provider": provider,
        "mode": mode,
        "chars": chars,
        "blocks": blocks,
        "estimated_cost": estimated,
        "allowed": allowed and estimated <= max_cost,
        "paid_enabled": paid_generation_allowed(),
        "max_cost": max_cost,
        "reason": "" if (allowed and estimated <= max_cost) else "Paid generation disabled or estimate exceeds budget."
    }
