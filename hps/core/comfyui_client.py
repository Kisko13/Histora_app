"""Minimal local ComfyUI hook. Talks only to localhost and never to paid image APIs."""
from __future__ import annotations
import json, urllib.request, uuid
from pathlib import Path

class ComfyUIClient:
    def __init__(self, host="http://127.0.0.1:8188", timeout=20):
        self.host = (host or "http://127.0.0.1:8188").rstrip("/")
        self.timeout = timeout
    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(self.host + "/system_stats", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False
    def queue_workflow(self, workflow: dict) -> str:
        payload = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode("utf-8")
        req = urllib.request.Request(self.host + "/prompt", data=payload, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            obj = json.loads(r.read().decode("utf-8"))
        return obj.get("prompt_id", "")

def write_comfy_prompt_pack(db, block_id: str, prompt: str) -> Path:
    folder = db.root_dir / "production" / "comfyui_prompts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{block_id}_prompt.txt"
    path.write_text(prompt or "", encoding="utf-8")
    return path
