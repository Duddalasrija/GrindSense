# AtomQuest 2026 Round 2 — GrindSense

## Project introduction

GrindSense is an outcome-oriented grinding concept prepared by Team Nexora for AtomQuest 2026 Round 2. The repository contains a navigable frontend and a FastAPI backend that simulate grinding sessions, along with SolidWorks mechanical concept CAD.

## Problem and proposed solution

Fixed-speed grinding gives limited visibility into changing load and progress. GrindSense explores a software workflow where a user selects a texture goal, observes generated process indicators, and sees explainable rule-based control responses. The current work demonstrates this workflow in software; it does not establish physical performance.

## Current prototype status

The prototype is software-only simulation with concept CAD. No physical mixer-grinder, motor controller, microphone, or sensors are connected. Current, load, vibration, temperature, acoustic-signature, torque-demand, texture, warnings, interlocks, and outcomes are simulated. No physical heat reduction, energy saving, real texture result, or safety protection has been measured or validated.

## Implemented frontend capabilities

The React and TypeScript application provides setup, live session, results, session history, and texture library views. Setup configures task/recipe, ingredient quantity and water, preparation, target texture, smoothness, adaptive mode, and demonstration scenario. The live and results views display generated estimates, event explanations, and session state; the UI identifies the prototype as simulation mode.

## Implemented backend capabilities

The FastAPI backend stores sessions, generated telemetry, and events in SQLite via SQLAlchemy. It exposes session creation and retrieval, history, start/pause/resume/stop lifecycle actions, telemetry/events/results endpoints, a simulation scenario default endpoint, and simulated interlock updates. A deterministic seeded generator produces virtual readings. The rule-based controller applies adaptive decisions, records threshold events, calculates short-term trend warnings, and can produce demonstration stop outcomes. These behaviors are software logic only.

## Mechanical concept work

`deliverables/cad/GrindSense_Concept/` contains SolidWorks files for a concept assembly, blade assembly, lid, mixer jar, and motor housing. These are design concept artefacts and do not demonstrate fabrication, fit, materials qualification, performance, or operational safety.

## System architecture

The React/TypeScript frontend sends JSON requests to the FastAPI service. The service manages each session, calls deterministic telemetry generation and rule-based adaptive logic, persists session state, readings, and events through SQLAlchemy to SQLite, and returns data for live and results views. See [architecture.md](architecture.md).

## Adaptive-control approach

For each simulated reading, the controller checks temperature, motor load, vibration, and acoustic-signature warning conditions in priority order, then a low-load progression case. It can modify virtual speed, intensity, and pulse/rest timing. Predictive trend logic examines a short history and emits warning/recovery events; it does not directly change controls. Critical thresholds and component interlocks can end or block a simulated session. Thresholds are demonstration parameters, not validated appliance limits. See [control_strategy.md](control_strategy.md).

## Demonstration workflow

1. Choose a recipe/task, quantity, water, preparation type, texture target, and optional adaptive mode and scenario.
2. The frontend creates a backend session and requests it to start.
3. The backend generates seeded readings at the configured interval and records relevant adaptive, warning, predictive, information, or safety events.
4. The frontend polls session, telemetry, and event endpoints and shows simulated live estimates.
5. On completion, stop, or simulated safety stop, the frontend presents the session results. History is read from persisted sessions.

## Current limitations

- There is no connection to a physical mixer-grinder, motor driver, microphone, or sensor.
- Simulated values and texture indices do not establish real measurements, accuracy, or appliance behavior.
- Thresholds, interlocks, and stop decisions are not certified protection.
- CAD has not been shown to be fabricated, fit-checked, material-qualified, or safety-reviewed.
- The repository includes test code, but this report does not state that tests or builds passed; they must be run against the relevant commit to verify them.

## Safety considerations

Do not interpret software interlocks or simulated stop events as hardware safety functions. Any future powered prototype would require appropriate guarding, an isolated and current-limited test setup, independent emergency stop and protection, qualified supervision, and formal design and risk review. Details are in [safety_and_risk.md](safety_and_risk.md).

## Validation approach

The software validation plan covers backend API and simulation tests, controller decisions, UI display behavior, API integration, session lifecycle, and edge cases. Physical validation is future work and would require calibrated sensors, repeatable ingredients and conditions, baseline and adaptive trials, and independent hardware safety checks. The plan is in [validation_plan.md](validation_plan.md).

## Future development roadmap

1. Run and record software verification against the final documentation/application commit.
2. Review and refine CAD packaging, clearances, materials, manufacturability, and serviceability.
3. Plan calibrated sensor acquisition using an isolated and appropriately guarded low-voltage bench setup.
4. Design and independently review a separate motor-control subsystem and physical protection before integration.
5. Establish repeatable baseline and adaptive trial protocols and acceptance criteria before collecting physical measurements.
6. Evaluate temperature rise, time-to-texture, repeatability, energy, current, response time, and warning/stop behavior only after safe instrumentation and protocols are established.

## Team Nexora

| S. No. | Student Name | Role |
|---:|---|---|
| 1 | Sai Spoorthy Eturu | Team Lead & Product/Repository Coordinator |
| 2 | Duddala Srija | Mechanical Concept & CAD Engineer |
| 3 | Katakam Sahithi Rithvika | UI/UX & Frontend Integration Engineer |
| 4 | Kommera Hari Hansika | Backend Simulation & Adaptive-Control Engineer |
| 5 | Gowravarapu Shamithri | Integration Support & Team Collaboration Coordinator |
