# V27.1 Production Control

This update replaces the broken patch-stack sections with complete production-ready files.

Included:

- repaired `studio_qt.py`
- safe batch production flow
- progress dialog + cancel support
- no broken indentation in `build_episode()`
- safe database row access
- clean voice generation path
- mock voice writes `.wav` + `voice_request.json`
- mock images/music write approved placeholder files in the paths used by project state detection
- image/music `.txt` placeholders count as approved assets

Test flow:

1. Start app with `run_studio_v24.bat`
2. Open/generated tagged script project
3. Provider = `mock`
4. Click `Generate Missing Assets`
5. Enter `3`
6. Expected: 3 voices, 3 images, 3 music placeholders generated, with report in `production/batch_report_latest.json`
