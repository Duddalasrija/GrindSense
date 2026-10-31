# GrindSense backend

Software-only FastAPI simulation. No physical appliance or sensors are connected; all telemetry, warning thresholds, texture scores and outcomes are estimates for demonstration.

## Run locally

From `backend/`:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs. SQLite database is created at `backend/grindsense.db`. Environment settings are listed in `.env.example`.

## Endpoints

`GET /api/health`; `POST /api/sessions`; `GET /api/sessions`; `GET /api/sessions/{id}`; `POST /api/sessions/{id}/start`; `POST /api/sessions/{id}/stop`; `GET /api/sessions/{id}/telemetry`; `GET /api/sessions/{id}/results`; `GET /api/sessions/{id}/events`; `POST /api/simulation/scenario`.

The backend generates coherent, seedable readings on a configurable interval and stores sessions, readings and events in SQLite. Scenarios: `normal`, `high_load`, `high_temperature`, `high_vibration`, `overload`. Thresholds in `app/main.py` are demonstration parameters only, not validated appliance safety limits.
