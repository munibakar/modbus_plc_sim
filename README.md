# Virtual PLC — Engine Modbus TCP Server

Simulates a real PLC monitoring an engine and exposes it over Modbus TCP
using `pymodbus`. A background task plays the role of the PLC's scan
cycle: every second it reads any operator commands, advances an internal
engine model, and republishes fresh sensor values.

## Install

```
pip install -r requirements.txt
```

## Run

```
python server.py
```

Listens on `0.0.0.0:5020` (use 502 instead if you have permission to bind
privileged ports / run as admin).

## Try it out

```
python client_test.py start 2200   # start the engine, target 2200 RPM
python client_test.py read         # stream live sensor values
python client_test.py stop         # stop the engine (values decay back to idle)
```

## Register map

All addresses are zero-based (`zero_mode=True`).

| Table              | Function codes | Address | Meaning                          |
|--------------------|-----------------|---------|-----------------------------------|
| Coil               | 01 / 05         | 0       | Engine start/stop command (write) |
| Discrete Input      | 02              | 0       | High temperature alarm            |
| Discrete Input      | 02              | 1       | High vibration alarm              |
| Discrete Input      | 02              | 2       | Low pressure alarm                |
| Input Register      | 04              | 0-1     | Temperature, °C (float32)         |
| Input Register      | 04              | 2-3     | Pressure, bar (float32)           |
| Input Register      | 04              | 4-5     | Vibration, mm/s (float32)         |
| Input Register      | 04              | 6-7     | Humidity, %RH (float32)           |
| Input Register      | 04              | 8-9     | RPM (float32)                     |
| Input Register      | 04              | 10-11   | Runtime, hours (float32)          |
| Holding Register    | 03 / 06 / 16    | 0       | Target RPM setpoint (uint16)      |

Float registers are big-endian byte order and big-endian word order
(standard "ABCD" layout).

## Notes on the simulation

`engine.py` models the engine as a first-order lag system: RPM chases the
target setpoint, and temperature/pressure/vibration/humidity all chase
values derived from the current load (RPM), each with its own time
constant plus random noise. Vibration also gets rare random spikes to
mimic imbalance events, and alarms trip automatically past realistic
thresholds (temperature > 100°C, vibration > 6 mm/s, pressure < 1 bar
while running).
