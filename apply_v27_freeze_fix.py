from pathlib import Path

ROOT = Path(__file__).resolve().parent

for p in (ROOT / "hps_qt").rglob("*.py"):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    old = txt

    # Replace heavy full refresh calls inside asset panels with lighter current-block refresh when possible
    txt = txt.replace("self.window().refresh_all()", "self.refresh()")
    txt = txt.replace("self.parent().refresh_all()", "self.refresh()")

    # Avoid opening folders/files with blocking shell wait patterns
    txt = txt.replace("subprocess.call(", "subprocess.Popen(")

    if txt != old:
        p.write_text(txt, encoding="utf-8")

studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

# Add lightweight refresh helper
if "def refresh_current_block_fast_v27" not in s:
    insert = s.find("    def refresh_all(self):")
    helper = '''
    def refresh_current_block_fast_v27(self):
        """Lightweight refresh after image/music/voice approve/import."""
        try:
            if self.selected_block_id:
                self.select_block(self.selected_block_id)
            if hasattr(self, "assistant_panel"):
                self.assistant_panel.refresh()
        except Exception:
            try:
                self.refresh_all()
            except Exception:
                pass

'''
    if insert != -1:
        s = s[:insert] + helper + s[insert:]

# Replace some expensive post-action full refreshes
s = s.replace("self.refresh_all(); self.auto_select_first_block()", "self.refresh_all(); self.auto_select_first_block()")
s = s.replace("self.refresh_all()\n            self.select_block(self.selected_block_id)", "self.refresh_current_block_fast_v27()")

studio.write_text(s, encoding="utf-8")

print("V27 freeze fix applied.")
print("Run: .\\run_studio_v24.bat")