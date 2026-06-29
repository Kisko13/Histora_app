from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import wave
import math
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class VoiceRequest:
    project_root: str
    block_id: str
    scene_id: str = ""
    scene_title: str = ""
    character: str = "narrator"
    voice_state: str = "narrator_slow"
    text: str = ""
    voice_style: str = "Deep restrained male narrator, slow immersive delivery"
    provider_hint: str = ""
    speed: float = 1.0
    emotion: str = "restrained"


@dataclass
class VoiceResult:
    ok: bool
    provider: str
    audio_path: str = ""
    error: str = ""
    seconds: float = 0.0
    cache_hit: bool = False
    meta_path: str = ""


class VoiceProvider:
    name = "base"
    def available(self) -> Tuple[bool, str]:
        return False, "not implemented"
    def generate(self, req: VoiceRequest, out_path: Path) -> VoiceResult:
        raise NotImplementedError


def _safe_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0


def _write_silence_or_tone_wav(path: Path, seconds: float = 2.0, sr: int = 48000, tone: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(max(0.25, seconds) * sr)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(frames):
            sample = 0
            if tone:
                sample = int(900 * math.sin(2 * math.pi * 220 * i / sr))
            w.writeframes(struct.pack("<h", sample))


class MockProvider(VoiceProvider):
    name = "mock"
    def available(self) -> Tuple[bool, str]:
        return True, "always available"
    def generate(self, req: VoiceRequest, out_path: Path) -> VoiceResult:
        # Short audible tone/silence placeholder. Keeps pipeline testable.
        seconds = max(1.25, min(8.0, len(req.text.split()) / 42.0))
        _write_silence_or_tone_wav(out_path, seconds=seconds, tone=True)
        return VoiceResult(True, self.name, str(out_path), seconds=_wav_duration(out_path))


class QwenDirectionProvider(VoiceProvider):
    """Qwen/Ollama is not a TTS engine. It can produce voice direction text only."""
    name = "qwen"
    def available(self) -> Tuple[bool, str]:
        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        try:
            import urllib.request
            with urllib.request.urlopen(host + "/api/tags", timeout=2.0) as r:
                if r.status == 200:
                    return True, "ollama reachable; direction-only provider"
        except Exception as e:
            return False, f"ollama unavailable: {e}"
        return False, "ollama unavailable"
    def generate(self, req: VoiceRequest, out_path: Path) -> VoiceResult:
        return VoiceResult(False, self.name, error="Qwen/Ollama is direction-only and cannot synthesize WAV audio.")


class PiperProvider(VoiceProvider):
    name = "piper"
    def available(self) -> Tuple[bool, str]:
        exe = os.getenv("PIPER_EXE", "").strip() or shutil.which("piper")
        model = os.getenv("PIPER_MODEL", "").strip()
        if not exe:
            return False, "PIPER_EXE not set and piper not in PATH"
        if not Path(exe).exists():
            return False, f"PIPER_EXE missing: {exe}"
        if not model or not Path(model).exists():
            return False, "PIPER_MODEL not set or missing"
        return True, f"{exe} | {model}"
    def generate(self, req: VoiceRequest, out_path: Path) -> VoiceResult:
        exe = os.getenv("PIPER_EXE", "").strip() or shutil.which("piper")
        model = os.getenv("PIPER_MODEL", "").strip()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [exe, "--model", model, "--output_file", str(out_path)]
        try:
            p = subprocess.run(cmd, input=req.text, text=True, capture_output=True, timeout=int(os.getenv("TTS_TIMEOUT_SEC", "180")))
            if p.returncode != 0 or not out_path.exists():
                return VoiceResult(False, self.name, error=(p.stderr or p.stdout or "piper failed")[-2000:])
            return VoiceResult(True, self.name, str(out_path), seconds=_wav_duration(out_path))
        except Exception as e:
            return VoiceResult(False, self.name, error=str(e))


class KokoroCliProvider(VoiceProvider):
    name = "kokoro"
    def available(self) -> Tuple[bool, str]:
        cmd = os.getenv("KOKORO_CMD", "").strip()
        if not cmd:
            return False, "KOKORO_CMD not set"
        return True, cmd
    def generate(self, req: VoiceRequest, out_path: Path) -> VoiceResult:
        # KOKORO_CMD may contain {text_file} and {out_file}. This keeps integration generic.
        cmd_template = os.getenv("KOKORO_CMD", "").strip()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        text_file = out_path.with_suffix(".txt")
        text_file.write_text(req.text, encoding="utf-8")
        cmd = cmd_template.format(text_file=str(text_file), out_file=str(out_path))
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=int(os.getenv("TTS_TIMEOUT_SEC", "240")))
            if p.returncode != 0 or not out_path.exists():
                return VoiceResult(False, self.name, error=(p.stderr or p.stdout or "kokoro failed")[-2000:])
            return VoiceResult(True, self.name, str(out_path), seconds=_wav_duration(out_path))
        except Exception as e:
            return VoiceResult(False, self.name, error=str(e))


PROVIDERS = {
    "qwen": QwenDirectionProvider,
    "piper": PiperProvider,
    "kokoro": KokoroCliProvider,
    "mock": MockProvider,
}


def load_dotenv(root: Path) -> None:
    env = root / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def provider_chain_from_env(default: str = "qwen,piper,kokoro,mock") -> List[str]:
    raw = os.getenv("VOICE_PROVIDER_CHAIN", "").strip() or os.getenv("TTS_PROVIDER_CHAIN", "").strip() or default
    return [x.strip().lower() for x in raw.replace("->", ",").split(",") if x.strip()]


def provider_health(chain: Optional[List[str]] = None) -> dict:
    chain = chain or provider_chain_from_env()
    items = []
    for name in chain:
        cls = PROVIDERS.get(name)
        if not cls:
            items.append({"provider": name, "available": False, "detail": "unknown provider"})
            continue
        ok, detail = cls().available()
        items.append({"provider": name, "available": ok, "detail": detail})
    return {"provider_chain": chain, "providers": items, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def cache_key(req: VoiceRequest, provider: str) -> str:
    payload = {
        "provider": provider,
        "text": req.text.strip(),
        "voice_state": req.voice_state,
        "character": req.character,
        "style": req.voice_style,
        "speed": req.speed,
        "emotion": req.emotion,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def generate_with_chain(req: VoiceRequest, chain: Optional[List[str]] = None, use_cache: bool = True) -> Tuple[VoiceResult, List[dict]]:
    root = Path(req.project_root)
    load_dotenv(root.parent.parent if root.name != "projects" else root)
    chain = chain or provider_chain_from_env()
    attempts = []
    raw_dir = root / "assets" / "audio_raw"
    cache_dir = root / "assets" / "voice_cache"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    for name in chain:
        cls = PROVIDERS.get(name)
        if not cls:
            attempts.append({"provider": name, "ok": False, "error": "unknown provider"})
            continue
        provider = cls()
        available, detail = provider.available()
        if not available:
            attempts.append({"provider": name, "ok": False, "error": detail})
            continue

        key = cache_key(req, name)
        cache_wav = cache_dir / f"{key}.wav"
        cache_meta = cache_dir / f"{key}.json"
        final_out = raw_dir / f"{req.block_id}_{req.character}_{name}_{int(time.time())}.wav"
        if use_cache and cache_wav.exists():
            shutil.copy2(cache_wav, final_out)
            res = VoiceResult(True, name, str(final_out), seconds=_wav_duration(final_out), cache_hit=True, meta_path=str(cache_meta))
            attempts.append({"provider": name, "ok": True, "cache_hit": True, "audio_rel_path": str(final_out.relative_to(root)).replace('\\', '/')})
            return res, attempts

        temp_out = cache_wav if use_cache else final_out
        res = provider.generate(req, temp_out)
        if res.ok and Path(res.audio_path).exists():
            if use_cache:
                _safe_write_json(cache_meta, {"request": asdict(req), "provider": name, "seconds": res.seconds, "cache_key": key})
                shutil.copy2(cache_wav, final_out)
                res.audio_path = str(final_out)
                res.meta_path = str(cache_meta)
            attempts.append({"provider": name, "ok": True, "cache_hit": res.cache_hit, "audio_rel_path": str(Path(res.audio_path).relative_to(root)).replace('\\', '/'), "seconds": res.seconds})
            return res, attempts
        attempts.append({"provider": name, "ok": False, "error": res.error})

    return VoiceResult(False, "none", error="all providers failed"), attempts
