from pathlib import Path

from .base import VoiceProvider
from hps.core.cost_control import paid_generation_allowed, estimate_voice_cost
from hps.providers.voice.qwen_client import synthesize_qwen_tts, qwen_config

class QwenVoiceProvider(VoiceProvider):
    name = "qwen"

    def synthesize(self, *, db, block_id):
        if not paid_generation_allowed():
            raise RuntimeError("Paid generation disabled. Set ALLOW_PAID_GENERATION=true in .env only when ready.")

        block = db.block(block_id)
        voice_state = db.one("SELECT * FROM voice_states WHERE id=?", (block["voice_state_id"],))
        voice_row = db.one("SELECT * FROM voices WHERE id=(SELECT actor_voice_id FROM characters WHERE id=?)", (block["character_id"],))

        version = (db.scalar("SELECT MAX(version) FROM audio_versions WHERE block_id=?", (block_id,)) or 0) + 1
        out_dir = db.root_dir / "assets" / "audio_raw"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{block_id}_qwen_v{version:03d}.wav"

        cfg = qwen_config()
        voice = cfg["default_voice"]
        if voice_row and voice_row["provider_voice_id"]:
            voice = voice_row["provider_voice_id"]

        instructions = voice_state["delivery_prompt"] if voice_state else None
        result = synthesize_qwen_tts(
            text=block["text"] or "",
            voice=voice,
            output_path=out,
            instructions=instructions,
            dry_run=False,
        )

        char_count = len(block["text"] or "")
        est = estimate_voice_cost(char_count, "qwen")

        if result.get("audio_path"):
            rel = str(Path(result["audio_path"]).relative_to(db.root_dir)).replace("\\", "/")
            audio_status = "generated"
            block_status = "generated"
        else:
            rel = str(Path(result.get("response_sidecar", out.with_suffix(".response.json"))).relative_to(db.root_dir)).replace("\\", "/")
            audio_status = result.get("status", "needs_inspection")
            block_status = "needs_inspection"

        db.execute(
            "INSERT INTO audio_versions(project_id, block_id, version, provider, path, status, char_count, estimated_cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (block["project_id"], block_id, version, self.name, rel, audio_status, char_count, est)
        )
        db.execute("UPDATE blocks SET status=?, issue=? WHERE id=?", (block_status, "" if block_status == "generated" else "Inspect Qwen response sidecar", block_id))
        return rel
