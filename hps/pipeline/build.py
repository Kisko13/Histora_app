import shutil
from hps.providers.voice.registry import get_voice_provider
from hps.core.cost_control import cost_guard

class BuildPipeline:
    def __init__(self, db, provider_name="mock", progress=None):
        self.db = db
        self.provider_name = provider_name
        self.provider = get_voice_provider(provider_name)
        self.progress = progress

    def generate_voice(self, mode="missing"):
        guard = cost_guard(self.db, mode, self.provider_name)
        if not guard["allowed"]:
            raise RuntimeError(
                f"Generation blocked. Provider={guard['provider']} blocks={guard['blocks']} "
                f"chars={guard['chars']} estimated=${guard['estimated_cost']:.4f}. {guard['reason']}"
            )
        rows = self.db.blocks() if mode == "all" else [r for r in self.db.blocks() if r["status"] == mode]
        total = len(rows)
        for i, block in enumerate(rows, start=1):
            if self.progress:
                self.progress(i, total, block["id"], f"Generating voice for {block['id']}")
            self.provider.synthesize(db=self.db, block_id=block["id"])
        return total

    def build_episode(self, mode="missing"):
        guard = cost_guard(self.db, mode, self.provider_name)
        steps = [
            ("Check project", True),
            ("Validate characters", True),
            ("Validate voices", True),
            (f"Cost estimate: ${guard['estimated_cost']:.4f} for {guard['blocks']} block(s)", True),
        ]
        generated = self.generate_voice(mode)
        steps.append((f"Generated {generated} voice block(s)", True))
        steps.append(("Images: local planning only", True))
        steps.append(("Music: local assignment only", True))
        return steps

    def approve_latest(self, block_id):
        row = self.db.one("SELECT * FROM audio_versions WHERE block_id=? ORDER BY version DESC LIMIT 1", (block_id,))
        if not row:
            raise RuntimeError(f"No audio version for {block_id}")
        src = self.db.root_dir / row["path"]
        out_dir = self.db.root_dir / "assets" / "audio_final"
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / f"{block_id}{src.suffix}"
        shutil.copy2(src, dst)
        rel = str(dst.relative_to(self.db.root_dir)).replace("\\", "/")
        self.db.execute("UPDATE blocks SET status='approved', approved_audio_path=?, issue='' WHERE id=?", (rel, block_id))
        self.db.execute("UPDATE audio_versions SET status='approved' WHERE id=?", (row["id"],))
        return rel
