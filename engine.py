"""Virtual engine model.

Produces temperature, pressure, vibration, humidity, RPM and runtime
readings that evolve over time the way a real engine's sensors would:
values ramp toward a target instead of jumping, they are correlated
with engine load, and they carry a bit of random noise plus rare
vibration spikes. This is what the Modbus server exposes to clients.
"""

from __future__ import annotations

import random


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _approach(current: float, target: float, dt: float, time_constant: float) -> float:
    """Move `current` toward `target` like a first-order lag (RC circuit)."""
    if time_constant <= 0:
        return target
    return current + (target - current) * min(1.0, dt / time_constant)


class VirtualEngine:
    """A small stateful model of an engine's sensor readings."""

    MIN_RPM = 0.0
    MAX_RPM = 3200.0

    def __init__(self) -> None:
        self.running = False
        self.rpm = 0.0
        self.target_rpm = 1800.0

        self.temperature = 22.0  # deg C, starts at ambient
        self.pressure = 0.0  # bar
        self.vibration = 0.1  # mm/s
        self.humidity = 45.0  # %RH
        self.runtime_hours = 0.0

        self.high_temperature_alarm = False
        self.high_vibration_alarm = False
        self.low_pressure_alarm = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def set_target_rpm(self, rpm: float) -> None:
        self.target_rpm = _clamp(rpm, 0, self.MAX_RPM)

    def tick(self, dt: float) -> None:
        """Advance the simulation by `dt` seconds."""
        rpm_target = self.target_rpm if self.running else 0.0
        self.rpm = _approach(self.rpm, rpm_target, dt, time_constant=6.0)
        self.rpm += random.uniform(-5, 5)
        self.rpm = _clamp(self.rpm, self.MIN_RPM, self.MAX_RPM)

        load = self.rpm / self.MAX_RPM  # 0..1

        target_temperature = 22.0 + load * 75.0
        self.temperature = _approach(self.temperature, target_temperature, dt, time_constant=25.0)
        self.temperature += random.uniform(-0.3, 0.3)

        target_pressure = 0.4 + load * 4.6
        self.pressure = _approach(self.pressure, target_pressure, dt, time_constant=4.0)
        self.pressure += random.uniform(-0.05, 0.05)
        self.pressure = max(0.0, self.pressure)

        target_vibration = 0.3 + load * 3.5
        spike = 4.0 if random.random() < 0.01 else 0.0  # rare imbalance/knock event
        self.vibration = _approach(self.vibration, target_vibration, dt, time_constant=2.0)
        self.vibration += random.uniform(-0.1, 0.1) + spike
        self.vibration = max(0.0, self.vibration)

        target_humidity = 50.0 - load * 8.0
        self.humidity = _approach(self.humidity, target_humidity, dt, time_constant=40.0)
        self.humidity += random.uniform(-0.2, 0.2)
        self.humidity = _clamp(self.humidity, 5.0, 95.0)

        if self.running:
            self.runtime_hours += dt / 3600.0

        self.high_temperature_alarm = self.temperature > 100.0
        self.high_vibration_alarm = self.vibration > 6.0
        self.low_pressure_alarm = self.running and self.pressure < 1.0
