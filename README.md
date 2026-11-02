# GrindSense — From Speed Control to Outcome Control

GrindSense is a software-only innovation prototype for adaptive grinding. A user selects coarse, medium, fine, or smooth. The simulation uses generated motor-current, load, vibration, temperature, acoustic-signature, and torque-demand proxy values to explain adaptive speed, intensity, pulsing, warnings, and stops. No physical mixer-grinder, motor controller, microphone, or sensors are connected. Telemetry, texture scores, warning limits, torque-demand indices, and outcomes are simulated estimates.

## Frontend

The React + Vite application is in `frontend/`. It implements the Figma setup, live simulation, results, history, and texture library screens using the downloaded design assets.

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` in `frontend/.env` only when the API is not running at `http://localhost:8000`.

## Backend

The FastAPI and SQLite simulation API is in `backend/`. Its README documents installation, demo scenarios, and available endpoints. Start it from `backend/` with:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive API documentation is available at http://localhost:8000/docs. API readings and outcomes are generated in software and do not represent hardware measurements.

## Design source

The UI references the connected GrindSense Figma file (`yY0BPF7ABoe23azHbvECLR`), including the outcome setup, live simulation, and session results frames. The original Figma file was not modified.
