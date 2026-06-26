"""Local Ollama/Qwen client. Free: talks only to localhost."""
from __future__ import annotations
import json, urllib.request, urllib.error
from dataclasses import dataclass

@dataclass
class OllamaResult:
    ok: bool
    text: str = ""
    error: str = ""

class OllamaClient:
    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://127.0.0.1:11434", timeout: int = 180):
        self.model = model or "qwen2.5:7b"
        self.host = (host or "http://127.0.0.1:11434").rstrip("/")
        self.timeout = int(timeout or 180)

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> OllamaResult:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": float(temperature)},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/generate", data=data, headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            obj = json.loads(raw)
            return OllamaResult(True, obj.get("response", ""), "")
        except Exception as exc:
            return OllamaResult(False, "", str(exc))

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False
