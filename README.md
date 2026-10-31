# GrindSense — From Speed Control to Outcome Control

GrindSense is a software-only innovation prototype for adaptive grinding. No physical mixer-grinder, motor controller, or sensors are connected. Telemetry, texture scores, warning limits, and outcomes are simulated estimates.

## Backend

The FastAPI and SQLite simulation API is in [backend/README.md](backend/README.md). It documents installation, demo scenarios, and all available endpoints. Start it from `backend/` with:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive API documentation is available at http://localhost:8000/docs.

## Design source

The intended interface follows the GrindSense Figma design. The Figma connection was unavailable during this backend foundation pass, so no design screens or visual assets are represented as inspected or implemented yet.
