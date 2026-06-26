# v15 State Refactor Test

1. Run `run_studio_v15.bat`.
2. Project should auto-select the first block.
3. Click B001 in the tree.
4. Open Image Studio.
5. Confirm it says `Current block: B001`.
6. Import image.
7. Confirm it saves to:

```text
projects/cannae_001/assets/images/B001/v001.png
```

8. Approve selected image.
9. Restart app.
10. Confirm B001 image state persists.
