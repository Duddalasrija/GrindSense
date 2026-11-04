# Adaptive grinding simulation strategy

## Purpose and scope

The controller in `backend/app/controller.py` is rule-based software logic for virtual sessions. It is not a trained machine-learning model and does not control a physical appliance. Inputs and outputs are simulated.

## Target texture

The user selects coarse, medium, fine, or smooth. `backend/app/simulation.py` generates a texture index from simulated progress, smoothness setting, and ingredient/task factors. Completion thresholds are 28, 52, 76, and 94 respectively. They are internal simulation values, not measured particle size or validated texture criteria.

## Simulated telemetry

The generator produces current, load, temperature, vibration, acoustic-signature index, torque-demand index, motor speed, texture index, and progress. A session seed and simulation tick provide deterministic variation. Demonstration scenarios alter simulated load, temperature, vibration, or acoustic signature. See [the data dictionary](../experiments/data_dictionary.md).

## Rule-based adaptive decisions

`adapt()` evaluates a reading in the following priority order:

1. At/above the simulated temperature warning condition, reduce virtual intensity and speed and use a longer rest pattern when the current intensity permits.
2. Otherwise, at/above simulated load warning, reduce virtual intensity and speed and lengthen rest.
3. Otherwise, at/above simulated vibration warning, reduce intensity and use shorter pulses.
4. Otherwise, at/above simulated acoustic-signature warning, reduce intensity and speed and use shorter pulses.
5. Otherwise, under lower simulated load and progress, gradually raise virtual intensity up to the configured cap.

If no condition calls for a change, the current simulated controls remain. An adaptive event stores the resulting control state and explanation. Exact thresholds and increments are implementation parameters, not calibrated values.

## Warning and predictive trend behavior

The controller records simulated threshold warning events for load, temperature, vibration, and acoustic-signature index. Predictive analysis uses up to the latest five readings and requires at least three. It calculates a least-squares slope, requires a rising majority trend, and estimates whether a configured threshold may be approached within three ticks. Predictive warning events are deduplicated per session and metric until values recover below the configured reset margin. A prediction records an event only; it does not directly adjust speed, intensity, session status, or stop behavior.

## Simulated stop decisions

A generated reading can cause a demonstration stop when it reaches the configured critical temperature, vibration, current, or load condition. Threshold evaluation takes precedence over target completion. These are virtual outcomes and do not provide physical protection. The separate simulated jar-present, lid-locked, and attachment-present booleans block start/resume when unsafe and can stop a running simulation when changed to unsafe.

## Session outcomes

A session can complete when the estimated texture index reaches the selected target. It can also end by user stop, a simulated critical threshold, or the backend's maximum tick limit. Outcomes and summary metrics are derived from stored simulated data, not appliance measurements.

## Interpretation limits

- Acoustic-signature values are unitless simulated proxies, not microphone readings or sound-pressure levels.
- Torque-demand values are unitless simulated proxies, not measured torque.
- Current, load, temperature, vibration, speed, texture, and progress are also generated estimates.
- Warning limits, interlocks, and stop outcomes are not certified or independently validated safety functions.
