"""
Mock real-time wastewater sensor.

The values are generated in memory so no hardware is required.
Set MOCK_SENSOR=true to use this simulator.
"""
import random
from datetime import datetime, timezone

_state = {
    "influent_cod": 300.0,
    "flow_rate": 50.0,
    "water_temp": 30.0,
    "current_do": 2.8,
}

def _drift(value, step, low, high):
    value += random.uniform(-step, step)
    return max(low, min(high, value))

def get_sensor_data():
    """Return one smooth-ish sensor sample."""
    # Small changes prevent the dashboard from jumping wildly.
    _state["influent_cod"] = _drift(_state["influent_cod"], 5.0, 180.0, 450.0)
    _state["flow_rate"] = _drift(_state["flow_rate"], 1.2, 30.0, 75.0)
    _state["water_temp"] = _drift(_state["water_temp"], 0.12, 26.0, 34.0)

    # Higher COD/flow slightly consumes oxygen; add natural process noise.
    oxygen_pressure = (
        (_state["influent_cod"] - 300.0) / 500.0
        + (_state["flow_rate"] - 50.0) / 150.0
    )
    target_do = 3.0 - oxygen_pressure * 0.55
    _state["current_do"] += (target_do - _state["current_do"]) * 0.12
    _state["current_do"] += random.uniform(-0.035, 0.035)
    _state["current_do"] = max(0.8, min(6.0, _state["current_do"]))

    return {
        "influent_cod": round(_state["influent_cod"], 2),
        "flow_rate": round(_state["flow_rate"], 2),
        "water_temp": round(_state["water_temp"], 2),
        "current_do": round(_state["current_do"], 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "mock_sensor",
    }
