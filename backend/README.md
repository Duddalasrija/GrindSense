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

`GET /api/health`; `POST /api/sessions`; `GET /api/sessions`; `GET /api/sessions/{id}`; `POST /api/sessions/{id}/start`; `POST /api/sessions/{id}/stop`; `POST /api/sessions/{id}/pause`; `POST /api/sessions/{id}/resume`; `POST /api/sessions/{id}/interlocks`; `GET /api/sessions/{id}/telemetry`; `GET /api/sessions/{id}/results`; `GET /api/sessions/{id}/events`; `POST /api/simulation/scenario`.

The backend generates coherent, seedable readings on a configurable interval and stores sessions, readings and events in SQLite. Scenarios: `normal`, `high_load`, `high_temperature`, `high_vibration`, `high_acoustic`, `overload`. Thresholds are demonstration parameters only, not validated appliance safety limits.

## Simulation and adaptive rules

Virtual signal generation lives in `app/simulation.py`; adaptive decisions and demo guardrails live in `app/controller.py`. Readings are reproducible from the session's `scenario_seed` and tick. Telemetry includes current, load, temperature, vibration, acoustic-signature index, torque-demand index, motor speed, texture index, progress, and timestamp. Events explain adaptive changes and safety actions. The acoustic signature and torque-demand values are unitless software proxies. They are not microphone recordings, measured sound levels, physical torque, or validated motor commands.

Texture completion uses the estimated texture index and these backend-owned minimum thresholds: Coarse `28`, Medium `52`, Fine `76`, Smooth `94`. A session completes when the index reaches the selected threshold. `smoothness_level` continues to affect the generated estimate and does not change these thresholds. Safety checks take precedence over texture completion.

Demo warnings are recorded at load `78`, temperature `72`, vibration `7`, and acoustic-signature index `68`. High acoustic signatures reduce simulated drive intensity and speed and use shorter pulses. Demo safety stops occur at load `96` or current `11.5`, temperature `88`, or vibration `11`. Simulated current is generated from load using an illustrative linear scale (`1.2 + load × 0.115`) with deterministic variation. The acoustic-signature index is generated from simulated load, vibration, and scenario inputs; the torque-demand index is a unitless proxy based on simulated load and intensity. Neither represents measured sound or torque. This lets the overload scenario demonstrate a current prediction and current stop before the separate load stop; it is not a physical electrical model. Current values and all thresholds are illustrative software values, not real appliance measurements or validated safety limits. Each warning category is recorded at most once per session.

### Predictive anomaly warnings

Predictive warnings analyse **simulated telemetry only** for motor load, temperature, vibration, acoustic-signature index, and motor current. The controller uses the latest five readings (at least three required), calculates a least-squares slope per simulation tick, and estimates whether the rising value may approach an existing warning or critical threshold within the next three ticks. Motor current uses its configured critical threshold because it has no separate warning threshold. A multi-step rising-trend check filters isolated spikes; stable, falling, and insufficient histories do not trigger predictions.

An eligible prediction is recorded as a separate `predictive_warning` event with warning severity and the existing event response fields. Its explanation identifies it as a `PREDICTIVE WARNING`, names the simulated metric, trend, threshold, and estimated ticks. A `predictive_recovery` informational event re-arms that metric after it falls at least 5% below its lowest configured threshold. Predictive deduplication is independent from threshold-warning deduplication. Predictive warnings do not alter control settings or session state. Existing threshold warnings and critical safety stops still evaluate each current reading and retain their behavior.

These estimates are short-term demonstrations from generated values; they are **not validated physical appliance predictions** and do not indicate measured hardware behavior or real-world prediction accuracy.

## Simulated jar, lid, and attachment interlocks

Sessions include three simulated component states: `jar_present`, `lid_locked`, and `attachment_present`. Each defaults to `true` for existing clients and existing SQLite rows, so requests that omit these fields remain compatible. These are simulated software states, not readings from physical sensors.

Pass an unsafe state when creating a session to demonstrate a blocked start:

```json
{
  "task_type": "chutney",
  "ingredients": ["coconut"],
  "jar_present": false,
  "lid_locked": true,
  "attachment_present": true
}
```

`POST /api/sessions/{id}/start` then returns HTTP 409 with a `detail` message naming every unsafe component. The session does not become `running`, no grinding telemetry tick is created, and a critical `safety` event is recorded using the existing event fields.

The additive endpoint `POST /api/sessions/{id}/interlocks` accepts all three booleans to update the simulated state:

```json
{"jar_present": true, "lid_locked": false, "attachment_present": true}
```

If any state becomes unsafe while running, the session is marked `safety_stopped`, a critical `safety` event explains the stop, and the simulation task is cancelled. The session response includes the three current booleans; telemetry and event response shapes are unchanged. SQLite startup adds the columns to existing databases with `true` defaults.

Run unit and API tests from `backend/` with `python -m pytest -q` after installing `requirements-dev.txt`.
