# GrindSense backend API

GrindSense is a **software-only simulation prototype**. No physical mixer-grinder, motor, controller, or sensors are connected. All telemetry, component states, thresholds, texture scores, predictions, and outcomes described here are generated or evaluated in software. They are illustrative values, not hardware measurements, validated appliance limits, or safety certification.

## Install and run

From the `backend/` directory, create and activate a virtual environment and install the runtime requirements:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API listens at `http://localhost:8000`. Interactive Swagger documentation is at `http://localhost:8000/docs`; the OpenAPI schema is at `http://localhost:8000/openapi.json`.

The default SQLite database is `backend/grindsense.db` when the app is started from `backend/`. Do not point `GRINDSENSE_DATABASE_URL` at a database you want to preserve during experiments. Existing SQLite databases receive backward-compatible session columns at startup for water, preparation, and the three simulated interlocks, plus telemetry columns for the simulated acoustic-signature and torque-demand proxies.

### Environment settings

| Variable | Default | Purpose |
|---|---|---|
| `GRINDSENSE_DATABASE_URL` | `sqlite:///./grindsense.db` | SQLAlchemy database URL |
| `GRINDSENSE_TICK_SECONDS` | `1.0` | Simulation interval in seconds; values are clamped to at least `0.25` |
| `GRINDSENSE_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed browser origins, including scheme and port |

For example, in PowerShell:

```powershell
$env:GRINDSENSE_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
uvicorn app.main:app --reload
```

The browser origin must match exactly. `localhost` and `127.0.0.1` are different origins.

### Run tests

Install development requirements and run the backend suite from `backend/`:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

To run tests against an isolated SQLite file instead of the default database:

```powershell
$env:GRINDSENSE_DATABASE_URL = "sqlite:///./.venv/test-grindsense.db"
python -m pytest -q
```

## API conventions

- JSON request bodies are used for session creation, scenario selection, and interlock updates.
- Session timestamps are returned as ISO-formatted datetimes. SQLite-backed responses may omit the timezone suffix; the application treats these stored values as UTC.
- Unknown session IDs return `404`. Invalid request data returns `422`. Lifecycle conflicts and unsafe start/resume attempts return `409`.
- Responses contain simulated state only; an HTTP success does not indicate interaction with an appliance.

## Endpoints

| Method and path | Purpose | Success response |
|---|---|---|
| `GET /api/health` | Report API and simulation mode | Health object |
| `POST /api/sessions` | Create a session | `201` and session object |
| `GET /api/sessions` | List sessions, newest first | Array of session objects |
| `GET /api/sessions/{sid}` | Retrieve one session | Session object |
| `POST /api/sessions/{sid}/start` | Start a created session, or start a paused session if safe | Session object |
| `POST /api/sessions/{sid}/pause` | Pause a running session | Session object |
| `POST /api/sessions/{sid}/resume` | Resume a paused session if safe | Session object |
| `POST /api/sessions/{sid}/stop` | Manually stop a running or paused session | Session object |
| `POST /api/sessions/{sid}/interlocks` | Update all three simulated component states | Session object |
| `GET /api/sessions/{sid}/telemetry` | Retrieve generated readings | Array of telemetry objects |
| `GET /api/sessions/{sid}/events` | Retrieve recorded events | Array of event objects |
| `GET /api/sessions/{sid}/results` | Retrieve the session summary and telemetry | Results object |
| `POST /api/simulation/scenario` | Set defaults for later sessions | Scenario object |

The JSON response examples below omit timestamps and some nullable fields where that keeps the example readable. Property names and types shown correspond to the API response.

### Health response

`GET /api/health` takes no request body and returns:

```json
{"status": "ok", "mode": "simulation", "hardware_connected": false}
```

## Session creation and session response

`POST /api/sessions` requires `ingredients`; other fields have the defaults and limits listed here.

| Field | Type | Default / accepted values |
|---|---|---|
| `task_type` | string | `chutney`; `chutney`, `masala`, `batter`, `custom` |
| `ingredients` | string array | Required; 1–12 entries |
| `quantity` | number | `250`; greater than 0 and at most 2000 |
| `added_water_ml` | number | `0`; 0–2000 |
| `preparation_type` | string | `Wet preparation`; `Wet preparation`, `Dry grinding`, `Blending` |
| `jar_present` | boolean | `true` |
| `lid_locked` | boolean | `true` |
| `attachment_present` | boolean | `true` |
| `target_texture` | string | `medium`; `coarse`, `medium`, `fine`, `smooth` |
| `smoothness_level` | integer | `50`; 0–100 |
| `adaptive_mode` | boolean | `true` |
| `simulation_scenario` | string | `normal`; `normal`, `high_load`, `high_temperature`, `high_vibration`, `high_acoustic`, `overload` |
| `scenario_seed` | integer | `42` |

Example request:

```http
POST /api/sessions
Content-Type: application/json
```

```json
{
  "task_type": "chutney",
  "ingredients": ["coconut", "chilli"],
  "quantity": 250,
  "added_water_ml": 80,
  "preparation_type": "Wet preparation",
  "jar_present": true,
  "lid_locked": true,
  "attachment_present": true,
  "target_texture": "smooth",
  "smoothness_level": 92,
  "adaptive_mode": true,
  "simulation_scenario": "normal",
  "scenario_seed": 42
}
```

Example session response (`201 Created`):

```json
{
  "id": "8dca2f1a-75dc-49c1-820a-49e66b54b70d",
  "task_type": "chutney",
  "ingredients": ["coconut", "chilli"],
  "quantity": 250.0,
  "added_water_ml": 80.0,
  "preparation_type": "Wet preparation",
  "jar_present": true,
  "lid_locked": true,
  "attachment_present": true,
  "target_texture": "smooth",
  "smoothness_level": 92,
  "adaptive_mode": true,
  "simulation_scenario": "normal",
  "status": "created",
  "progress": 0.0,
  "started_at": null,
  "completed_at": null,
  "estimated_texture_score": null,
  "result_summary": null
}
```

Session objects returned from create, history, retrieval, and lifecycle endpoints use the same fields. `started_at`, `completed_at`, `estimated_texture_score`, and `result_summary` can be null before they are set.

If `simulation_scenario` or `scenario_seed` is omitted, the current defaults from `POST /api/simulation/scenario` are used. Otherwise their values in the create request are used.

## Session lifecycle

Typical flow:

```text
created --start--> running --pause--> paused
running --stop--> stopped
paused --stop--> stopped
paused --resume--> running
running --texture target reached--> completed
running --critical guardrail reached--> safety_stopped
running --unsafe interlock update--> safety_stopped
running --180 ticks reached--> completed
```

`stopped`, `completed`, and `safety_stopped` are terminal: attempting to start them again returns `409`. The `start` endpoint also accepts a paused, safe session; `resume` is the explicit paused-session operation. `pause` changes state only when the session is running; otherwise it returns the current session unchanged. `stop` transitions a running or paused session to `stopped` and records one informational event. Repeating stop on an already stopped session returns the unchanged session without another event; stop requests on created, completed, or safety-stopped sessions are also no-op `200` responses. `resume` returns `409` unless the session is paused and its interlocks are safe.

Lifecycle-control endpoints (`start`, `pause`, `resume`, and `stop`) take no request body. The backend changes a session's state to `running` when started/resumed. It then generates one simulated telemetry reading per tick until it reaches a terminal state. Texture completion and safety-stop checks run for each generated reading; a critical safety stop is checked before texture completion.

## Telemetry and results

`GET /api/sessions/{sid}/telemetry` returns an array. Each reading contains:

```json
{
  "timestamp": "2026-11-02T12:00:01",
  "motor_current": 8.14,
  "motor_load": 60.4,
  "temperature": 31.2,
  "vibration": 3.1,
  "acoustic_signature_index": 47.8,
  "torque_demand_index": 43.5,
  "motor_speed": 648.0,
  "texture_index": 1.7,
  "progress": 1.8
}
```

Readings are generated in `app/simulation.py`. A session seed and tick initialize deterministic variation, so the same scenario, seed, and session state generate repeatable telemetry. Scenarios adjust virtual load, temperature, vibration, or acoustic signature. `acoustic_signature_index` is a unitless simulated proxy derived from load, vibration, intensity, and deterministic variation; it is not a microphone recording or measured sound level. `torque_demand_index` is a unitless simulated proxy based on load and intensity; it is not physical torque. In the `high_acoustic` scenario, simulated load and acoustic signature are raised. In the `overload` scenario, the regression test uses seed `19` to demonstrate a motor-current prediction and current-triggered stop before the separate load critical threshold. Current is generated as `1.2 + simulated_load × 0.115` plus deterministic variation in `[-0.1, 0.1]`; this illustrative relation is not an electrical model.

`GET /api/sessions/{sid}/results` returns the session fields plus:

```json
{
  "duration_seconds": 12.0,
  "max_motor_load": 78.4,
  "max_temperature": 35.1,
  "max_acoustic_signature_index": 58.2,
  "max_torque_demand_index": 56.1,
  "adaptive_actions": 2,
  "telemetry": []
}
```

`telemetry` has the same reading objects as the telemetry endpoint. Duration is null if either start or completion time is unset. The route can be called for any existing session and summarizes whatever readings are stored at that time. Acoustic-signature and torque-demand maxima are simulated proxy indices, not measured sound or physical torque.

## Adaptive control, texture targets, and safety

`app/controller.py` makes adaptive decisions from each simulated reading. Its priority is temperature, then load, then vibration, then acoustic signature. When the acoustic-signature index reaches its warning threshold, the controller can reduce simulated intensity and speed and use a shorter pulse pattern. Depending on the simulated reading and session state it changes simulated speed and intensity, selects a pulse pattern, and records an `adaptive` event with an explanation. Low load with low progress can raise intensity gradually. Predictive warnings themselves do not modify controls or session state.

Texture completion uses the estimated texture index and these backend-owned minimum thresholds:

| Texture | Completion threshold |
|---|---:|
| `coarse` | 28 |
| `medium` | 52 |
| `fine` | 76 |
| `smooth` | 94 |

`smoothness_level` influences generated texture progression but does not replace these target thresholds.

Warning thresholds are load `78`, temperature `72`, vibration `7`, and acoustic-signature index `68`. Critical simulated stops occur at load `96`, motor current `11.5`, temperature `88`, or vibration `11`; there is no acoustic-signature critical stop threshold. Threshold checks run on each current reading; critical safety stops take precedence over texture completion. Values are illustrative software parameters only, not validated limits for a real appliance.

## Predictive anomaly warnings

Predictive analysis uses only simulated motor load, temperature, vibration, acoustic-signature index, and current. It considers at most the latest five readings and requires three. A least-squares slope and a multi-step rising trend check estimate whether an existing warning or critical threshold may be reached within three simulation ticks. The acoustic-signature index uses its existing warning threshold of `68`. Current has a critical threshold but no separate warning threshold, so its critical value is used.

Qualifying predictions generate a separate `predictive_warning` event with `warning` severity. A metric remains deduplicated until its value recovers at least 5% below its lowest configured threshold; a `predictive_recovery` event with `info` severity records re-arming. Deduplication is per session and metric. Predictive events do not suppress real-time threshold warning or safety checks. These are short-term estimates from generated values, not validated physical appliance predictions.

## Simulated jar, lid, and attachment interlocks

`jar_present`, `lid_locked`, and `attachment_present` are simulated booleans, not physical sensor readings. All default to `true` for backward compatibility with clients that omit them and existing SQLite rows.

An unsafe create request is accepted, but `POST /api/sessions/{sid}/start` returns `409` and a `detail` message naming each unsafe component. The session remains unstarted, has no grinding telemetry tick, and records a critical `safety` event.

Example update request:

```http
POST /api/sessions/{sid}/interlocks
Content-Type: application/json
```

```json
{
  "jar_present": true,
  "lid_locked": false,
  "attachment_present": true
}
```

Making a component unsafe during a running session cancels its simulation task, sets status to `safety_stopped`, and records a critical `safety` event. Updating a paused or created session to an unsafe state records a warning; it cannot be started/resumed until safe. Interlocks cannot be changed on a terminal session (`409`). These software interlocks do not certify or provide physical hardware safety.

## Events

`GET /api/sessions/{sid}/events` returns events in insertion order. Every object uses this shape; state snapshots may be null when not applicable:

```json
{
  "timestamp": "2026-11-02T12:00:01",
  "event_type": "predictive_warning",
  "previous_state": {"metric": "temperature", "value": 70.0},
  "new_state": {
    "metric": "temperature",
    "status": "active",
    "threshold": 72,
    "slope_per_tick": 0.8,
    "estimated_ticks_to_threshold": 2.5
  },
  "severity": "warning",
  "explanation": "PREDICTIVE WARNING: Simulated temperature is rising and may approach the configured threshold."
}
```

Event types used by the backend include `adaptive`, `warning`, `safety`, `predictive_warning`, `predictive_recovery`, and `info`. Explanations describe simulated decisions or conditions. Threshold warning categories are recorded at most once per session; predictive warning/recovery deduplication is separate.

## Scenario defaults

`POST /api/simulation/scenario` sets defaults for future session creations that omit scenario fields. It does not change existing sessions or persist a scenario setting separately from session data.

Request:

```json
{"scenario": "high_temperature", "seed": 42}
```

Response:

```json
{
  "scenario": "high_temperature",
  "seed": 42,
  "note": "Applied as the default for sessions created without an explicit scenario."
}
```

Allowed scenarios are `normal`, `high_load`, `high_temperature`, `high_vibration`, `high_acoustic`, and `overload`. The `high_acoustic` scenario raises the simulated acoustic-signature proxy and associated simulated load; it does not capture or measure sound.

## Errors

| Status | Meaning | Typical cases |
|---:|---|---|
| `404 Not Found` | The session ID does not exist | Session, telemetry, event, lifecycle, interlock, or results route with unknown ID |
| `409 Conflict` | The requested lifecycle operation is not allowed | Start a stopped/completed/safety-stopped session; unsafe start/resume; resume a non-paused session; update interlocks on a terminal session |
| `422 Unprocessable Entity` | Request body does not satisfy its schema | Missing/too many ingredients, out-of-range numeric values, unsupported task/texture/scenario values, or missing interlock booleans |

FastAPI error responses include a `detail` field. A 409 from an unsafe start includes component-specific reasons. For a 422, FastAPI returns its validation details.
