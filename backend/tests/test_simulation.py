from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from app.controller import adapt, predictive_warnings, safety_stop_reason, warning_reasons
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


@pytest.mark.parametrize(
    ("metric", "values", "threshold"),
    [
        ("motor_load", [72, 74, 76], 78),
        ("temperature", [66, 68, 70], 72),
        ("vibration", [5.5, 5.9, 6.4], 7),
        ("motor_current", [9.5, 10.0, 10.7], 11.5),
    ],
)
def test_rising_metrics_predict_configured_threshold_approach(metric, values, threshold):
    readings = [reading(**{metric: value}) for value in values]
    predictions = predictive_warnings(readings)
    prediction = next(item for item in predictions if item.metric == metric)
    assert prediction.threshold == threshold
    assert prediction.slope_per_tick > 0
    assert 0 < prediction.estimated_ticks_to_threshold <= 3


@pytest.mark.parametrize("values", [[60, 60, 60, 60, 60], [60, 61, 62, 63, 64]])
def test_stable_or_slowly_rising_values_without_near_threshold_crossing_do_not_predict(values):
    predictions = predictive_warnings([reading(motor_load=value) for value in values])
    assert not any(item.metric == "motor_load" for item in predictions)


def test_falling_values_do_not_predict():
    predictions = predictive_warnings([reading(motor_load=value) for value in [76, 74, 72, 70, 68]])
    assert not any(item.metric == "motor_load" for item in predictions)


def test_fewer_than_three_readings_do_not_predict():
    predictions = predictive_warnings([reading(motor_load=value) for value in [72, 76]])
    assert not predictions


def test_single_noisy_spike_does_not_predict():
    predictions = predictive_warnings([reading(motor_load=value) for value in [70, 70, 70, 70, 77]])
    assert not any(item.metric == "motor_load" for item in predictions)


def test_prediction_at_exactly_three_ticks_is_included_and_later_crossing_is_excluded():
    exact = predictive_warnings([reading(motor_load=value) for value in [63, 66, 69]])
    prediction = next(item for item in exact if item.metric == "motor_load")
    assert prediction.threshold == 78
    assert prediction.estimated_ticks_to_threshold == pytest.approx(3)

    beyond = predictive_warnings([reading(motor_load=value) for value in [60, 63, 66]])
    assert not any(item.metric == "motor_load" for item in beyond)


def test_only_latest_five_readings_influence_prediction():
    values = [110, 0, 110, 0, 70, 72, 74, 76, 77]
    predictions = predictive_warnings([reading(motor_load=value) for value in values])
    prediction = next(item for item in predictions if item.metric == "motor_load")
    assert prediction.slope_per_tick == pytest.approx(1.8)
    assert prediction.estimated_ticks_to_threshold == pytest.approx(1 / 1.8)


def test_existing_sqlite_session_rows_get_safe_interlock_defaults():
    from app.main import ensure_sqlite_session_columns

    legacy_engine = create_engine("sqlite://")
    try:
        with legacy_engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE grinding_sessions (id VARCHAR PRIMARY KEY)")
        ensure_sqlite_session_columns(legacy_engine)
        with legacy_engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO grinding_sessions (id) VALUES ('legacy-session')")
            values = connection.exec_driver_sql(
                "SELECT jar_present, lid_locked, attachment_present FROM grinding_sessions WHERE id='legacy-session'"
            ).one()
        assert values == (1, 1, 1)
    finally:
        legacy_engine.dispose()
