# AtomQuest 2026 Round 2 submission checklist

**Deadline:** 4 November 2026, 23:59 IST
**Required public-round deliverable:** one 90-second video showing the current project progress.
**Official round page:** https://gradpartners.in/e/atomquest-2026-339

The public AtomQuest page says shortlisted teams submit a 90-second current-progress video. It refers teams to the case study sent with the Round 1 results for the detailed submission rules. Follow that case study if it specifies anything beyond this checklist; the linked PDF could not be rendered in this environment.

## What is already in the repository

- React + TypeScript dashboard and FastAPI + SQLite backend.
- Software simulation for coarse, medium, fine, and smooth target textures.
- Demonstrations for changing simulated readings, adaptive responses, warnings, stops, simulated interlocks, pause/resume/stop, results, and session history.
- A previously checked software build and test run recorded in `ROUND2_STATUS.md`.
- Clear in-product and README disclosure that this is software-only and no appliance or sensor is connected.

## Must finish before recording

- [ ] Open the app with both frontend and backend running; verify the dashboard connects.
- [ ] Record a real screen capture of a normal session: choose a texture, start, show readings changing, then show results/history.
- [ ] Record one clearly labelled simulated warning or overload scenario if it runs reliably.
- [ ] Complete and review the current mesh-only concept: make editable housing, jar, blade, and lid parts; mate them in the assembly; create a native exploded configuration; label proposed sensor/interlock locations and illustrative dimensions.
- [ ] Capture genuine SOLIDWORKS screenshots after the assembly and exploded configuration are complete. Until then, identify the current parts and SVG as early concept visuals, not a finished CAD model.
- [ ] State plainly that the readings and safety responses are simulated and the physical appliance is not yet connected.
- [ ] Keep the finished video at or under 90 seconds and save a local copy before submission.
- [ ] Review the Round 1 result email/case-study PDF for any submission format or portal instructions not shown on the public event page.
- [ ] Submit the video through the official AtomQuest submission route before the deadline; confirm the portal shows successful submission.

## Do not claim in the video

- That any sensor or motor controller is physically connected.
- That a real grinder changed speed, temperature, vibration, or texture in response to the software.
- That simulated thresholds are appliance safety limits or validated performance measurements.
- That the CAD model represents a manufactured or safety-reviewed product.

## Local demo startup

Use two terminals from the repository root.

Backend terminal (after installing `backend/requirements.txt` into the chosen Python environment):

```powershell
cd backend
uvicorn app.main:app --reload
```

Frontend terminal:

```powershell
cd frontend
npm run dev
```

Open the Vite URL printed by the frontend. The UI should show **Simulation mode** and **No device connected or required**. If the API is offline, stop and fix that before recording.
