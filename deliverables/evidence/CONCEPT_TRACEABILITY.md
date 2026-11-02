# Approved concept traceability

| Approved concept item | Current status | Evidence / limitation |
|---|---|---|
| Coarse, medium, fine, smooth user outcome | Implemented in the software UI and simulation response | Four selectable outcomes; software mapping only, not validated food outcomes. |
| Sense and interpret current/load, vibration, temperature | Simulated | Software-generated indices and scenario values, no connected sensors. |
| Acoustic signature | Simulated proxy | Unitless synthetic `acoustic_signature_index`; no microphone, dB measurement, or real acoustic signal. |
| Torque adaptation | Partial software proxy | Unitless `torque_demand_index`; no torque sensor, verified torque control, or physical motor control. |
| Adapt speed/intensity/pulsing and respond to heat/load | Simulated | Controller rules and tests exercise software responses; no hardware validation. |
| Predict warning, reduce intensity, stop on severe/overload states | Simulated guardrails | Tests cover API/controller behavior; thresholds are not appliance safety limits. |
| Verify target outcome and stop | Partial simulation | Software run/result flow and completion criteria exist; actual ingredient texture is not sensed or validated. |
| Jar, lid, attachment interlocks | Simulated state checks | No physical switches or interlock hardware is verified. |
| Noise/heat reduction and reliable grinding | Not physically demonstrated | No measurement or comparative hardware test evidence. |
| Garlic peeling / coconut grating attachments | Future extension | Not implemented or physically modeled/validated. |
| Concept CAD layout and exploded assembly | Incomplete | No finished CAD files or authentic CAD screenshots are included in this branch. |
