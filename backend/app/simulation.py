"""Deterministic virtual telemetry for the software-only GrindSense prototype."""

import math
import random
from typing import Any


TEXTURE_THRESHOLDS: dict[str, float] = {
    "coarse": 28,
    "medium": 52,
    "fine": 76,
    "smooth": 94,
}

# Illustrative virtual scaling chosen so the current guardrail is reachable
# before the separate simulated load guardrail in the overload scenario.
MOTOR_CURRENT_PER_LOAD = 0.115


def generate_reading(session: Any) -> dict[str, float]:
    """Generate one reproducible reading from persisted session state.

    A session's seed and tick determine random variation, so replaying the same
    scenario and session state yields identical simulated values.
    """
    rng = random.Random(session.scenario_seed + session.tick * 7919)
    task_factor = {"chutney": 1, "masala": 0.92, "batter": 0.85, "custom": 0.95}.get(
        session.task_type, 0.95
    )
    ingredient_factors = {"coconut": 1.12, "chilli": 1, "spices": 0.9, "lentils": 1.14}
    ingredient_factor = task_factor * sum(
        ingredient_factors.get(name.lower(), 1) for name in session.ingredients
    ) / len(session.ingredients)

    load = (
        38
        + ingredient_factor * 14
        + math.sin(session.tick / 5) * 2.4
        + session.intensity * 8
        + rng.uniform(-1.2, 1.2)
    )
    temperature = 28 + session.tick * (0.22 + session.intensity * 0.13) + max(0, load - 60) * 0.12
    vibration = 2.1 + abs(math.sin(session.tick / 3)) * 1.1 + max(0, load - 65) * 0.07

    if session.simulation_scenario == "high_load":
        load += min(32, session.tick * 1.3)
    if session.simulation_scenario == "high_temperature":
        temperature += session.tick * 0.43
    if session.simulation_scenario == "high_vibration":
        vibration += min(9.5, session.tick * 0.38)
    if session.simulation_scenario == "high_acoustic":
        load += min(18, session.tick * 0.55)
    if session.simulation_scenario == "overload":
        load += min(65, session.tick * 2.7)

    load = max(8, min(110, load))
    acoustic_signature_index = max(
        0,
        min(
            120,
            22 + load * 0.2 + vibration * 2 + session.intensity * 8
            + (min(48, session.tick * 1.8) if session.simulation_scenario == "high_acoustic" else 0)
            + rng.uniform(-1.5, 1.5),
        ),
    )
    torque_demand_index = max(0, min(100, load * session.intensity))
    progress = min(
        100,
        session.progress
        + (0.60 + session.intensity * 0.8)
        * (1.08 if session.simulation_scenario == "normal" else 0.85)
        * ingredient_factor,
    )
    texture_index = min(
        100,
        progress * (0.72 + session.smoothness_level / 250) * min(1.12, ingredient_factor),
    )

    return {
        "motor_current": round(1.2 + load * MOTOR_CURRENT_PER_LOAD + rng.uniform(-0.1, 0.1), 2),
        "motor_load": round(load, 1),
        "temperature": round(temperature, 1),
        "vibration": round(vibration, 1),
        "acoustic_signature_index": round(acoustic_signature_index, 1),
        "torque_demand_index": round(torque_demand_index, 1),
        "motor_speed": round(max(300, session.speed_rpm * session.intensity + rng.uniform(-12, 12))),
        "texture_index": round(texture_index, 1),
        "progress": round(progress, 1),
    }


def texture_complete(texture: str, texture_index: float) -> bool:
    """Return whether the estimated texture index reached its selected target."""
    try:
        threshold = TEXTURE_THRESHOLDS[texture]
    except KeyError as exc:
        raise ValueError(f"Unsupported target texture: {texture}") from exc
    return texture_index >= threshold
