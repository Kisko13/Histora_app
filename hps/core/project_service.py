from hps.storage.db import ProjectDB

class ProjectService:
    def __init__(self):
        self.db = None

    def open(self, path):
        self.db = ProjectDB(path).connect()
        return self.db

    def save_block(self, block_id, character_id, voice_state_id, scene_label, text, image_prompt="", music_cue="", notes=""):
        self.db.execute(
            "UPDATE blocks SET character_id=?, voice_state_id=?, scene_label=?, text=?, image_prompt=?, music_cue=?, notes=? WHERE id=?",
            (character_id, voice_state_id, scene_label, text, image_prompt, music_cue, notes, block_id)
        )

    def set_block_status(self, block_id, status, issue=""):
        self.db.execute("UPDATE blocks SET status=?, issue=? WHERE id=?", (status, issue, block_id))

    def set_image_status(self, block_id, status):
        self.db.execute("UPDATE blocks SET image_status=? WHERE id=?", (status, block_id))

    def set_music_status(self, block_id, status):
        self.db.execute("UPDATE blocks SET music_status=? WHERE id=?", (status, block_id))
