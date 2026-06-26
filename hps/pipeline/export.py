import csv

def export_capcut_csv(db):
    export_dir = db.root_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out = export_dir / "capcut_audio_import_order.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order", "scene", "block_id", "character", "voice_state", "status", "approved_audio", "image_prompt", "music_cue", "text_preview"])
        for idx, b in enumerate(db.blocks(), start=1):
            w.writerow([idx, b["scene_title"], b["id"], b["character_id"], b["voice_state_id"], b["status"], b["approved_audio_path"], b["image_prompt"], b["music_cue"], (b["text"][:140] + "...").replace("\n", " ")])
    project = db.project()
    if project:
        db.execute("INSERT INTO exports(project_id, export_type, path) VALUES (?, 'capcut_csv', ?)", (project["id"], str(out.relative_to(db.root_dir)).replace("\\","/")))
    return out
