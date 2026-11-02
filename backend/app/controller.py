"""Adaptive control and demo safety decisions for virtual GrindSense sessions."""

from dataclasses import dataclass
from typing import Any


WARN_LOAD = 78
WARN_TEMPERATURE = 72
WARN_VIBRATION = 7
WARN_ACOUSTIC = 68
CRITICAL_LOAD = 96
CRITICAL_TEMPERATURE = 88
CRITICAL_VIBRATION = 11
CRITICAL_CURRENT = 11.5
PREDICTIVE_WINDOW_SIZE = 5
PREDICTIVE_MIN_READINGS = 3
PREDICTIVE_HORIZON_TICKS = 3
PREDICTIVE_RESET_MARGIN = 0.05

PREDICTIVE_THRESHOLDS = {
    "motor_load": (WARN_LOAD, CRITICAL_LOAD),
    "temperature": (WARN_TEMPERATURE, CRITICAL_TEMPERATURE),
    "vibration": (WARN_VIBRATION, CRITICAL_VIBRATION),
    "acoustic_signature_index": (WARN_ACOUSTIC,),
    "motor_current": (CRITICAL_CURRENT,),
}


@dataclass(frozen=True)
class ControlDecision:
    speed_rpm: float
    intensity: float
    pulse_pattern: str
    explanation: str | None


@dataclass(frozen=True)
class PredictiveWarning:
    metric: str
    threshold: float
    slope_per_tick: float
    estimated_ticks_to_threshold: float


def predictive_warnings(readings: list[dict[str, float]]) -> list[PredictiveWarning]:
    """Predict near-term approaches to configured thresholds from simulated readings.

    Uses an ordinary least-squares slope over at most the latest five readings.
    A majority-trend check filters isolated one-reading spikes; estimates are
    demonstration signals, not physical predictions.
    """
    window = readings[-PREDICTIVE_WINDOW_SIZE:]
    if len(window) < PREDICTIVE_MIN_READINGS:
        return []

    predictions = []
    x_mean = (len(window) - 1) / 2
    x_variance = sum((x - x_mean) ** 2 for x in range(len(window)))
    for metric, thresholds in PREDICTIVE_THRESHOLDS.items():
        values = [float(item[metric]) for item in window]
        y_mean = sum(values) / len(values)
        slope = sum((x - x_mean) * (value - y_mean) for x, value in enumerate(values)) / x_variance
        positive_steps = sum(right > left for left, right in zip(values, values[1:]))
        minimum_positive_steps = max(2, (len(values) - 1) // 2 + 1)
        if slope <= 0 or positive_steps < minimum_positive_steps:
            continue

        current = values[-1]
        for threshold in thresholds:
            gap = threshold - current
            ticks = gap / slope
            if 0 < ticks <= PREDICTIVE_HORIZON_TICKS:
                predictions.append(PredictiveWarning(metric, threshold, slope, ticks))
                break
    return predictions


def adapt(session: Any, reading: dict[str, float]) -> ControlDecision:
    """Compute the next simulated control settings using the existing priority."""
    speed = session.speed_rpm
    intensity = session.intensity
    pulse = session.pulse_pattern
    message = None

    if reading["temperature"] >= WARN_TEMPERATURE and intensity > 0.52:
        intensity = 0.48
        speed = max(420, speed - 120)
        pulse = "2s on / 2s rest"
        message = "Temperature rising. Reducing simulated intensity and extending rest pulses."
    elif reading["motor_load"] >= WARN_LOAD and intensity > 0.45:
        intensity = 0.43
        speed = max(420, speed - 150)
        pulse = "2s on / 2s rest"
        message = "High simulated grinding load detected. Reducing intensity and speed and extending rest pulses."
    elif reading["vibration"] >= WARN_VIBRATION and intensity > 0.4:
        intensity = 0.38
        pulse = "1s on / 2s rest"
        message = "Abnormal simulated vibration detected. Reducing intensity and using shorter pulses."
    elif reading["acoustic_signature_index"] >= WARN_ACOUSTIC and intensity > 0.4:
        intensity = 0.38
        speed = max(420, speed - 80)
        pulse = "1s on / 2s rest"
        message = "Elevated simulated acoustic signature. Reducing drive intensity and using shorter pulses."
    elif reading["motor_load"] < 62 and session.progress < 70 and intensity < 0.82:
        intensity = min(0.82, intensity + 0.04)
        message = "Load is stable and texture progress is low. Gradually increasing simulated intensity."

    return ControlDecision(speed, intensity, pulse, message)


def warning_reasons(reading: dict[str, float]) -> list[tuple[str, str]]:
    """Return warning event type and plain-language explanation for a reading."""
    warnings = []
    if reading["motor_load"] >= WARN_LOAD:
        warnings.append(("load", "High simulated motor load warning; demonstration threshold only."))
    if reading["temperature"] >= WARN_TEMPERATURE:
        warnings.append(("temperature", "Simulated temperature warning; demonstration threshold only."))
    if reading["vibration"] >= WARN_VIBRATION:
        warnings.append(("vibration", "Abnormal simulated vibration warning; demonstration threshold only."))
    if reading["acoustic_signature_index"] >= WARN_ACOUSTIC:
        warnings.append(("acoustic", "Elevated simulated acoustic signature warning; demonstration threshold only."))
    return warnings


def safety_stop_reason(reading: dict[str, float]) -> str | None:
    """Return the highest-priority simulated protective stop reason, if any."""
    if reading["temperature"] >= CRITICAL_TEMPERATURE:
        return "Critical simulated temperature threshold reached; session stopped safely. Demo threshold only."
    if reading["vibration"] >= CRITICAL_VIBRATION:
        return "Critical abnormal simulated vibration threshold reached; session stopped safely. Demo threshold only."
    if reading["motor_current"] >= CRITICAL_CURRENT:
        return "Simulated motor overload: critical motor-current threshold reached; session stopped safely. Demo threshold only."
    if reading["motor_load"] >= CRITICAL_LOAD:
        return "Simulated motor overload threshold reached; session stopped safely. Demo threshold only."
    return None
