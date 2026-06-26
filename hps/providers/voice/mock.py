from .base import VoiceProvider

class MockVoiceProvider(VoiceProvider):
    name = "mock"

    def synthesize(self, *, db, block_id):
        block = db.block(block_id)
        scene = db.scene_for_block(block_id)
        project = db.project()
        voice_state = db.one("SELECT * FROM voice_states WHERE id=?", (block["voice_state_id"],))
        character = db.one("SELECT * FROM characters WHERE id=?", (block["character_id"],))
        version = (db.scalar("SELECT MAX(version) FROM audio_versions WHERE block_id=?", (block_id,)) or 0) + 1
        out_dir = db.root_dir / "assets" / "audio_raw"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{block_id}_v{version:03d}.txt"
        char_count = len(block["text"] or "")
        out.write_text(
            f"MOCK AUDIO — FREE\n\nPROJECT: {project['title'] if project else ''}\n"
            f"SCENE: {scene['title'] if scene else ''}\nBLOCK: {block_id}\n"
            f"CHARACTER: {block['character_id']}\nVOICE_STATE: {block['voice_state_id']}\n\n"
            f"CHARACTER BASELINE:\n{character['baseline'] if character else ''}\n\n"
            f"DELIVERY:\n{voice_state['delivery_prompt'] if voice_state else ''}\n\n"
            f"SCRIPT:\n{block['text']}\n",
            encoding="utf-8"
        )
        rel = str(out.relative_to(db.root_dir)).replace("\\", "/")
        db.execute(
            "INSERT INTO audio_versions(project_id, block_id, version, provider, path, status, char_count, estimated_cost_usd) VALUES (?, ?, ?, ?, ?, 'generated', ?, 0)",
            (block["project_id"], block_id, version, self.name, rel, char_count)
        )
        db.execute("UPDATE blocks SET status='generated', issue='' WHERE id=?", (block_id,))
        return rel
