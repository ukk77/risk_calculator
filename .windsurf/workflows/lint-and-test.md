---
description: Lint and test the Risk Calculator FastAPI service
---

1. Verify the FastAPI app imports cleanly from `c:\Users\ukard\OneDrive\Desktop\trading`:
   `risk_calculator\venv\Scripts\python.exe -c "from backend.app.main import app; print('Import OK')"`

2. Run the contract validation tests with pytest from `c:\Users\ukard\OneDrive\Desktop\trading\risk_calculator`:
   `risk_calculator\venv\Scripts\python.exe -m pytest tests/test_contracts.py -v`
   If pytest is not installed: `risk_calculator\venv\Scripts\python.exe -m pip install pytest --quiet` then re-run.

3. Run flake8 linting across the backend (skip if not installed):
   `risk_calculator\venv\Scripts\python.exe -m flake8 backend --select=E,W --max-line-length=120 --statistics --count`

4. Optionally verify the CLI risk report entry point works (does not start the server):
   `risk_calculator\venv\Scripts\python.exe cli.py --help`

5. Report any import errors, test failures, or lint violations found.
