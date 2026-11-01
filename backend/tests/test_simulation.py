from types import SimpleNamespace

import pytest

from app.controller import adapt, safety_stop_reason, warning_reasons
from app.simulation import TEXTURE_THRESHOLDS, generate_reading, texture_complete


def session(**overrides):
    values = {
        "scenario_seed": 19,
        "tick": 1,
        "task_type": "chutney",
        "ingredients": ["coconut", "chilli"],
        "intensity": 0.72,
        "speed_rpm": 900,
        "pulse_pattern": "3s on / 1s rest",
        "progress": 0,
        "smoothness_level": 55,
        "simulation_scenario": "normal",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def reading(**overrides):
    values = {
        "motor_current": 5.0,
        "motor_load": 60.0,
        "temperature": 40.0,
        "vibration": 3.0,
        "motor_speed": 650.0,
        "texture_index": 20.0,
        "progress": 10.0,
    }
    values.update(overrides)
    return values


def test_normal_grinding_generates_complete_telemetry():
    result = generate_reading(session())
    assert set(result) == {
        "motor_current", "motor_load", "temperature", "vibration",
        "motor_speed", "texture_index", "progress",
    }
    assert 8 <= result["motor_load"] <= 110
    assert result["motor_current"] > 0
    assert result["progress"] > 0


def test_high_load_scenario_increases_load_and_warns():
    normal = generate_reading(session(tick=30))
    high = generate_reading(session(tick=30, simulation_scenario="high_load"))
    assert high["motor_load"] > normal["motor_load"]
    assert any(key == "load" for key, _ in warning_reasons(reading(motor_load=80)))


def test_high_temperature_scenario_and_warning():
    normal = generate_reading(session(tick=30))
    hot = generate_reading(session(tick=30, simulation_scenario="high_temperature"))
    assert hot["temperature"] > normal["temperature"]
    assert any(key == "temperature" for key, _ in warning_reasons(reading(temperature=72)))


def test_high_vibration_scenario_and_warning():
    normal = generate_reading(session(tick=30))
    rough = generate_reading(session(tick=30, simulation_scenario="high_vibration"))
    assert rough["vibration"] > normal["vibration"]
    assert any(key == "vibration" for key, _ in warning_reasons(reading(vibration=7)))


def test_overload_scenario_reaches_safety_stop():
    result = generate_reading(session(tick=30, simulation_scenario="overload"))
    assert result["motor_load"] >= 96 or result["motor_current"] >= 11.5
    assert "overload" in safety_stop_reason(result).lower()


@pytest.mark.parametrize("texture,threshold", TEXTURE_THRESHOLDS.items())
def test_each_texture_completes_at_its_backend_threshold(texture, threshold):
    assert not texture_complete(texture, threshold - 0.1)
    assert texture_complete(texture, threshold)
    assert texture_complete(texture, threshold + 1)


def test_temperature_adaptation_reduces_speed_intensity_and_changes_pulse():
    decision = adapt(session(), reading(temperature=73))
    assert decision.speed_rpm == 780
    assert decision.intensity == 0.48
    assert decision.pulse_pattern == "2s on / 2s rest"
    assert "Temperature" in decision.explanation


def test_load_adaptation_reduces_speed_intensity_and_changes_pulse():
    decision = adapt(session(), reading(motor_load=80))
    assert decision.speed_rpm == 750
    assert decision.intensity == 0.43
    assert decision.pulse_pattern == "2s on / 2s rest"


def test_vibration_adaptation_reduces_intensity_and_shortens_pulses():
    decision = adapt(session(), reading(vibration=8))
    assert decision.speed_rpm == 900
    assert decision.intensity == 0.38
    assert decision.pulse_pattern == "1s on / 2s rest"


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"motor_load": 96}, "overload"),
        ({"temperature": 88}, "temperature"),
        ({"vibration": 11}, "vibration"),
        ({"motor_current": 11.5}, "overload"),
    ],
)
def test_critical_conditions_have_clear_stop_reasons(values, expected):
    assert expected in safety_stop_reason(reading(**values)).lower()


def test_same_seed_and_state_generate_identical_readings():
    state = session(scenario_seed=456, tick=17, simulation_scenario="high_vibration")
    assert generate_reading(state) == generate_reading(state)


def test_unknown_texture_is_rejected():
    with pytest.raises(ValueError, match="Unsupported target texture"):
        texture_complete("silky", 100)
