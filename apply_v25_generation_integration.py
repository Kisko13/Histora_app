from pathlib import Path

ROOT = Path(__file__).resolve().parent

wizard = ROOT / "hps_qt" / "dialogs" / "project_wizard.py"
w = wizard.read_text(encoding="utf-8")

# 1) Add generated_project_path field
w = w.replace(
    "        self.generated = False",
    "        self.generated = False\n        self.generated_project_path = None"
)

# 2) Patch generate_project to store latest plan JSON and expose path
old = '''            importer = ScriptImporter(self.db)
            legacy_plan = plan_to_legacy_importer_shape(self.plan)
            result = importer.apply_plan(legacy_plan, replace_existing=True)
            self.generated = True
            QMessageBox.information(
                self,
                "Project Generated",
                f"Created {result['scenes']} scene(s) and {result['blocks']} block(s).\\n\\n"
                f"Source: {result['source']}"
            )
            self.accept()'''

new = '''            importer = ScriptImporter(self.db)
            legacy_plan = plan_to_legacy_importer_shape(self.plan)
            result = importer.apply_plan(legacy_plan, replace_existing=True)

            # Save the full V25 production analysis beside the .hps project.
            try:
                import json
                project_path = Path(str(self.db.path))
                production_dir = project_path.parent / "production"
                production_dir.mkdir(parents=True, exist_ok=True)
                latest_plan_path = production_dir / "script_plan_latest.json"
                latest_plan_path.write_text(
                    json.dumps(self.plan, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception:
                pass

            self.generated = True
            self.generated_project_path = Path(str(self.db.path))

            QMessageBox.information(
                self,
                "Project Generated",
                f"Created {result['scenes']} scene(s) and {result['blocks']} block(s).\\n\\n"
                f"Source: {result['source']}\\n\\n"
                f"The project will now reload in the main studio."
            )
            self.accept()'''

if old not in w:
    raise RuntimeError("Could not find generate_project block to replace.")

w = w.replace(old, new)
wizard.write_text(w, encoding="utf-8")


studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

old = '''        if dlg.exec() and getattr(dlg, "generated", False):
            self.project_label.setText(str(self.db.path))
            p = self.db.project()
            self.title_label.setText(p["title"] if p else "Historical POV Studio")
            self.refresh_all()
            self.auto_select_first_block()'''

new = '''        if dlg.exec() and getattr(dlg, "generated", False):
            generated_path = getattr(dlg, "generated_project_path", None)

            if generated_path:
                # Reopen the generated project so all main-studio panels refresh from disk.
                self.open_project(Path(generated_path))
            else:
                self.project_label.setText(str(self.db.path))
                p = self.db.project()
                self.title_label.setText(p["title"] if p else "Historical POV Studio")
                self.refresh_all()
                self.auto_select_first_block()'''

if old not in s:
    raise RuntimeError("Could not find open_project_wizard refresh block.")

s = s.replace(old, new)
studio.write_text(s, encoding="utf-8")


doc = ROOT / "docs" / "V25_GENERATION_INTEGRATION.md"
doc.write_text("""# V25 Generation Integration

Adds final integration after Production Plan approval:

1. Generated project auto-loads in the main studio.
2. Main scene tree, dashboard, block workspace, and mission control refresh automatically.
3. Full V25 production plan is saved beside the `.hps` project:

`production/script_plan_latest.json`

This makes the New Project Wizard part of the real production workflow.
""", encoding="utf-8")

print("V25 generation integration applied.")
print("Run: .\\run_studio_v24.bat")