# Validation plan

## Status

This document describes checks to perform; it does not claim they have been executed. Test files exist in `backend/tests/` and `frontend/tests/`. Record command output and the exact commit when validation is performed.

## Backend API tests

From `backend/`, install `requirements-dev.txt` and run `python -m pytest -q`. Cover request validation, response contracts, health mode, endpoint status codes, persistence, history, results, and unknown session handling. Use an isolated SQLite URL for local tests as described in `backend/README.md`.

## Simulation tests

Exercise seeded repeatability, scenario-specific changes, telemetry schema, texture progression and completion thresholds, generated ranges where implemented, and session termination behavior. Confirm that test expectations describe simulated values only.

## Controller behavior tests

Check priority ordering for temperature, load, vibration, and acoustic-signature rules; speed/intensity/pulse updates; adaptive event explanations; warning thresholds; predictive trend detection, deduplication and recovery; and simulated critical stops. Confirm that predictive warnings alone do not change controls or status.

## Frontend checks

Run the existing display helper test from `frontend/` with `node --test tests/display.test.mjs`. Run `npm run build` to check TypeScript compilation and Vite production bundling. These commands are documented, not reported as passed here.

## API integration checks

With the backend and frontend running, exercise the user workflow from session setup through live polling, event display, results, and history. Verify that `VITE_API_URL` and backend CORS origins match the browser/API addresses. Confirm that UI labels identify values as simulated and proxy indices.

## Session lifecycle validation

Check created -> running -> paused -> resumed -> stopped paths, target completion, safety_stopped conditions, terminal-session restrictions, unsafe simulated interlocks at start/resume, and interlock changes during running. Verify telemetry and event recording and confirm that task cancellation prevents additional readings after a stop.

## Edge cases

Include invalid and boundary request values, missing and unknown IDs, repeated stop requests, attempts to restart terminal sessions, conflicting lifecycle requests, each unsafe interlock, multiple unsafe components, scenario changes for later sessions, and empty/short history for predictive checks.

## Hardware validation — future work

No physical tests have been run or claimed. Before any hardware integration, define a reviewed protocol for isolated and guarded low-voltage testing, sensor calibration, independent protection, repeatable baseline/adaptive trials, ingredients and environmental conditions, texture acceptance criteria, and data handling. Future evaluation may measure temperature rise, time-to-texture, repeatability, energy, motor current, control response, and warning/stop behavior. Do not publish improvement claims until appropriately designed trials produce and verify the measurements.
