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

The backend generates coherent, seedable readings on a configurable interval and stores sessions, readings and events in SQLite. Scenarios: `normal`, `high_load`, `high_temperature`, `high_vibration`, `overload`. Thresholds are demonstration parameters only, not validated appliance safety limits.

## Simulation and adaptive rules

Virtual signal generation lives in `app/simulation.py`; adaptive decisions and demo guardrails live in `app/controller.py`. Readings are reproducible from the session's `scenario_seed` and tick. The API response shape remains unchanged: telemetry includes current, load, temperature, vibration, motor speed, texture index, progress, and timestamp; events explain adaptive changes and safety actions.

Texture completion uses the estimated texture index and these backend-owned minimum thresholds: Coarse `28`, Medium `52`, Fine `76`, Smooth `94`. A session completes when the index reaches the selected threshold. `smoothness_level` continues to affect the generated estimate and does not change these thresholds. Safety checks take precedence over texture completion.

Demo warnings are recorded at load `78`, temperature `72`, and vibration `7`. Demo safety stops occur at load `96` or current `11.5`, temperature `88`, or vibration `11`. These values are illustrative software thresholds, not validated appliance safety limits. Each warning category is recorded at most once per session.

Run unit and API tests from `backend/` with `python -m pytest -q` after installing `requirements-dev.txt`.
