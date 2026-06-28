# V27 Batch Production Control

Adds:

- Generate Missing Assets
- test limit prompt: 0 = all, 5 = first 5 missing per type
- runs voice/image/music queues together
- saves `production/batch_report_latest.json`
- keeps mock/offline workflow free except future real voice providers

Test recommendation:

1. Set provider to mock.
2. Click Generate Missing Assets.
3. Enter 5.
4. Confirm 5 voices, 5 images, 5 music placeholders generated.
5. Check production/batch_report_latest.json.
