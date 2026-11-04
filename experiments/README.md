# GrindSense simulated experiments

## Scope

This directory documents the virtual telemetry used by the GrindSense software-only simulation. It does not contain physical experiment results or a fabricated dataset. No physical mixer-grinder, motor controller, microphone, or sensors are connected.

## Generation approach

`backend/app/simulation.py` generates one telemetry record per simulation tick from session state. Scenario, task type, ingredients, current virtual intensity and speed, progress, tick, and seed influence values. A local pseudo-random generator seeded from session seed and tick provides repeatable variation for a given virtual state. Scenarios include normal, high_load, high_temperature, high_vibration, high_acoustic, and overload.

The controller evaluates those generated readings with rule-based conditions in `backend/app/controller.py`. It records software events and estimates only. Scenario names do not indicate real appliance testing.

## Data interpretation

The telemetry names and display units are described in the [data dictionary](data_dictionary.md). Acoustic-signature and torque-demand values are unitless simulated proxies; they are not actual microphone readings or measured physical torque. The UI presents current, load, temperature, vibration, and speed in familiar units, but these remain generated software estimates. Texture index and progress are model values, not measurements of ingredient particles or grinding performance.

Expected ranges are included only when constrained by the generator or explicitly represented by the UI. Where no explicit clamp or validated range exists, no expected physical range is asserted.

## Reproducing a demonstration

Create a session with a chosen `simulation_scenario` and `scenario_seed` using the API described in [backend/README.md](../backend/README.md). The same seed and tick reproduce the pseudo-random component for the same virtual state; different adaptive state or task configuration can change the resulting values. Scenario defaults set through the API affect later session creations that omit scenario fields.

## Limitations

- No physical measurements, trials, or performance improvements are reported here.
- Virtual values are not sensor accuracy, real temperature, physical torque, sound level, current characterization, or energy use.
- Model formulas and demonstration thresholds are not calibrated physical models or safe operating limits.
- Do not infer appliance safety, texture accuracy, energy savings, or heat reduction from simulated outcomes.
