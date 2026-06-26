SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    youtube_title_draft TEXT,
    runtime_target TEXT,
    description_status TEXT DEFAULT 'missing',
    thumbnail_status TEXT DEFAULT 'missing',
    music_status TEXT DEFAULT 'missing',
    export_status TEXT DEFAULT 'missing',
    assembly_status TEXT DEFAULT 'missing',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    visual_theme TEXT,
    music_profile TEXT,
    sfx_profile TEXT,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    role TEXT,
    actor_voice_id TEXT,
    baseline TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS voices (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    display_name TEXT,
    provider TEXT,
    provider_voice_id TEXT,
    source_audio_path TEXT,
    clone_status TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS voice_states (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    delivery_prompt TEXT
);

CREATE TABLE IF NOT EXISTS blocks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    character_id TEXT,
    voice_state_id TEXT,
    scene_label TEXT,
    text TEXT,
    status TEXT DEFAULT 'missing',
    issue TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    approved_audio_path TEXT DEFAULT '',
    image_status TEXT DEFAULT 'missing',
    image_prompt TEXT DEFAULT '',
    music_status TEXT DEFAULT 'missing',
    music_cue TEXT DEFAULT '',
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    block_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    provider TEXT,
    path TEXT,
    status TEXT DEFAULT 'generated',
    char_count INTEGER DEFAULT 0,
    estimated_cost_usd REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    export_type TEXT,
    path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
