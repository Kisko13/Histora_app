from PySide6.QtWidgets import QTextEdit
class SmartInspector(QTextEdit):
    def __init__(self): super().__init__(); self.setReadOnly(True)
    def show_project(self,db):
        p=db.project(); voice_done,voice_total=db.voice_progress(); img_done,img_total=db.image_progress(); mus_done,mus_total=db.music_progress()
        runtime=db.runtime_seconds_estimate()
        self.setPlainText(f"""EPISODE OVERVIEW

Title:
{p['title'] if p else ''}

Runtime estimate:
{runtime//60}m {runtime%60}s

Scenes:
{len(db.scenes())}

Blocks:
{db.total_blocks()}

Characters:
{len(db.characters())}

Voices:
{len(db.voices())}

Voice:
{voice_done}/{voice_total}

Images:
{img_done}/{img_total}

Music:
{mus_done}/{mus_total}

Estimated Spend:
${db.total_estimated_spend():.4f}

Assistant:
Local / rule-based / free
""")
    def show_block(self,block,versions):
        spend=sum([v["estimated_cost_usd"] for v in versions])
        self.setPlainText(f"""BLOCK {block['id']}

Scene:
{block['scene_title']}

Character:
{block['character_id']}

Delivery:
{block['voice_state_id']}

Voice:
{block['status']}

Image:
{block['image_status']}

Music:
{block['music_status']}

Issue:
{block['issue'] or '-'}

Approved Audio:
{block['approved_audio_path'] or '-'}

Versions:
{len(versions)}

Spend:
${spend:.4f}
""")
