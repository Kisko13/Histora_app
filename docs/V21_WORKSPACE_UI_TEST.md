# v21 Workspace UI Test

1. Run `run_studio_v21.bat`.
2. Confirm main tabs are:
   - Produce
   - Project
   - AI
   - Control
3. Open Control -> Production Queue.
4. Click Do Next Task.
5. Expected:
   - missing voice opens voice dialog
   - missing image moves to Produce -> Image Studio
   - missing music moves to Produce -> Music Studio
6. Right side should show Mission Control / current queue.
