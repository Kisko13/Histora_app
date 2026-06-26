import sqlite3
from pathlib import Path
from .schema import SCHEMA_SQL

class ProjectDB:
    def __init__(self, path):
        self.path = Path(path)
        self.conn = None

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self._migrate()
        self.conn.commit()
        return self

    def _migrate(self):
        tables = {
            "project": [
                ("description_status", "TEXT DEFAULT 'missing'"),
                ("thumbnail_status", "TEXT DEFAULT 'missing'"),
                ("music_status", "TEXT DEFAULT 'missing'"),
                ("export_status", "TEXT DEFAULT 'missing'"),
                ("assembly_status", "TEXT DEFAULT 'missing'"),
            ],
            "blocks": [
                ("image_status", "TEXT DEFAULT 'missing'"),
                ("image_prompt", "TEXT DEFAULT ''"),
                ("music_status", "TEXT DEFAULT 'missing'"),
                ("music_cue", "TEXT DEFAULT ''"),
            ],
            "audio_versions": [
                ("char_count", "INTEGER DEFAULT 0"),
                ("estimated_cost_usd", "REAL DEFAULT 0"),
            ],
        }
        for table, cols in tables.items():
            existing = [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            for col, spec in cols:
                if col not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {spec}")

        # V24: durable production orchestration tables.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS production_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                block_id TEXT DEFAULT '',
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                dependency_key TEXT DEFAULT '',
                attempt_count INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                estimated_cost_usd REAL DEFAULT 0,
                result_path TEXT DEFAULT '',
                message TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS production_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

    @property
    def root_dir(self):
        return self.path.parent

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql, params=()):
        row = self.one(sql, params)
        return row[0] if row else None

    def upsert_project(self, project_id, title, youtube_title_draft="", runtime_target=""):
        self.execute("""
            INSERT INTO project(id, title, youtube_title_draft, runtime_target)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                youtube_title_draft=excluded.youtube_title_draft,
                runtime_target=excluded.runtime_target,
                updated_at=CURRENT_TIMESTAMP
        """, (project_id, title, youtube_title_draft, runtime_target))

    def project(self):
        return self.one("SELECT * FROM project LIMIT 1")

    def scenes(self):
        return self.query("SELECT * FROM scenes ORDER BY sort_order")

    def characters(self):
        return self.query("SELECT * FROM characters ORDER BY id")

    def voices(self):
        return self.query("SELECT * FROM voices ORDER BY id")

    def blocks(self):
        return self.query("""
            SELECT b.*, s.title AS scene_title
            FROM blocks b
            JOIN scenes s ON s.id = b.scene_id
            ORDER BY s.sort_order, b.sort_order
        """)

    def block(self, block_id):
        return self.one("SELECT * FROM blocks WHERE id=?", (block_id,))

    def block_with_scene(self, block_id):
        return self.one("""
            SELECT b.*, s.title AS scene_title
            FROM blocks b JOIN scenes s ON s.id=b.scene_id
            WHERE b.id=?
        """, (block_id,))

    def scene_for_block(self, block_id):
        return self.one("SELECT s.* FROM scenes s JOIN blocks b ON b.scene_id=s.id WHERE b.id=?", (block_id,))

    def audio_versions(self, block_id):
        return self.query("SELECT * FROM audio_versions WHERE block_id=? ORDER BY version DESC", (block_id,))

    def counts(self):
        rows = self.query("SELECT status, COUNT(*) AS n FROM blocks GROUP BY status")
        return {r["status"]: r["n"] for r in rows}

    def total_blocks(self):
        return self.scalar("SELECT COUNT(*) FROM blocks") or 0

    def approved_count(self):
        return self.scalar("SELECT COUNT(*) FROM blocks WHERE status='approved'") or 0

    def generated_count(self):
        return self.scalar("SELECT COUNT(*) FROM blocks WHERE status='generated'") or 0

    def missing_count(self):
        return self.scalar("SELECT COUNT(*) FROM blocks WHERE status='missing'") or 0

    def redo_count(self):
        return self.scalar("SELECT COUNT(*) FROM blocks WHERE status='redo'") or 0

    def completion_percent(self):
        total = self.total_blocks()
        return int((self.approved_count() / total) * 100) if total else 0

    def story_progress(self):
        total = self.total_blocks()
        ready = self.scalar("SELECT COUNT(*) FROM blocks WHERE text IS NOT NULL AND TRIM(text)!=''") or 0
        return ready, total

    def voice_progress(self):
        from hps.core.block_state import approved_voice_path
        total = self.total_blocks()
        done = sum(1 for b in self.blocks() if approved_voice_path(self, b["id"]))
        return done, total

    def image_progress(self):
        from hps.core.block_state import approved_image_path
        total = self.total_blocks()
        done = sum(1 for b in self.blocks() if approved_image_path(self, b["id"]))
        return done, total

    def music_progress(self):
        from hps.core.block_state import approved_music_path
        total = self.total_blocks()
        done = sum(1 for b in self.blocks() if approved_music_path(self, b["id"]))
        return done, total

    def assembly_progress(self):
        p = self.project()
        return (1, 1) if p and p["assembly_status"] == "approved" else (0, 1)

    def export_progress(self):
        exported = self.scalar("SELECT COUNT(*) FROM exports") or 0
        return (1 if exported else 0), 1

    def next_recommended_block(self):
        from hps.core.block_state import compute_project_state
        state = compute_project_state(self)
        return {"id": state["next"]["block_id"]} if state["next"] else None

    def estimate_chars_for_mode(self, mode):
        rows = self.blocks() if mode == "all" else [r for r in self.blocks() if r["status"] == mode]
        return sum(len(r["text"] or "") for r in rows), len(rows)

    def total_estimated_spend(self):
        return self.scalar("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM audio_versions") or 0

    def runtime_seconds_estimate(self):
        return sum(max(3, int(len(b["text"] or "") / 13)) for b in self.blocks())

    # ----------------------------- V24 production jobs -----------------------------
    def project_id(self):
        p = self.project()
        return p["id"] if p else "project"

    def production_jobs(self):
        return self.query("SELECT * FROM production_jobs ORDER BY id")

    def clear_production_jobs(self):
        self.execute("DELETE FROM production_jobs")

    def add_production_job(self, task_type, block_id="", status="pending", dependency_key="", estimated_cost_usd=0.0, message=""):
        return self.execute(
            """INSERT INTO production_jobs(project_id, block_id, task_type, status, dependency_key, estimated_cost_usd, message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self.project_id(), block_id or "", task_type, status, dependency_key or "", float(estimated_cost_usd or 0), message or "")
        ).lastrowid

    def update_production_job(self, job_id, **fields):
        if not fields:
            return
        allowed = {"status", "dependency_key", "attempt_count", "max_attempts", "estimated_cost_usd", "result_path", "message"}
        assignments, values = [], []
        for k, v in fields.items():
            if k in allowed:
                assignments.append(f"{k}=?")
                values.append(v)
        if not assignments:
            return
        assignments.append("updated_at=CURRENT_TIMESTAMP")
        values.append(job_id)
        self.execute(f"UPDATE production_jobs SET {', '.join(assignments)} WHERE id=?", tuple(values))

    def set_production_setting(self, key, value):
        self.execute("""INSERT INTO production_settings(key,value) VALUES (?,?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, str(value)))

    def get_production_setting(self, key, default=""):
        row = self.one("SELECT value FROM production_settings WHERE key=?", (key,))
        return row["value"] if row else default

    def timeline_rows(self):
        rows = []
        current = 0
        for b in self.blocks():
            seconds = max(3, int(len(b["text"] or "") / 13))
            rows.append({"start": current, "end": current + seconds, "duration": seconds, "block": b})
            current += seconds
        return rows
