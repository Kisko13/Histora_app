# v18 Assembly Studio Test

1. Run `run_studio_v18.bat`.
2. Approve at least one voice and one image for B001.
3. Open Assembly Studio.
4. Click Refresh Assembly.
5. Expected:
   - B001 READY if voice + image are approved.
   - Music is shown but optional.
6. Click Export Manifest.
7. Check:

```text
projects/cannae_001/exports/assembly/assembly_manifest.json
projects/cannae_001/exports/assembly/assembly_manifest.csv
```

Next milestone after this:
- v19: simple MP4/CapCut assembly export.
