"""Quick manual test client for the virtual PLC server.

Usage:
    python client_test.py read            # poll and print sensor values
    python client_test.py start [rpm]     # start the engine, optional target RPM
    python client_test.py stop            # stop the engine
"""

from __future__ import annotations

import sys
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

HOST = "127.0.0.1"
PORT = 5020

SENSOR_NAMES = ["temperature", "pressure", "vibration", "humidity", "rpm", "runtime_hours"]


def read_sensors(client: ModbusTcpClient) -> dict:
    result = client.read_input_registers(address=0, count=12, slave=1)
    decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
    values = {name: decoder.decode_32bit_float() for name in SENSOR_NAMES}

    alarms = client.read_discrete_inputs(address=0, count=3, slave=1)
    values["high_temperature_alarm"] = alarms.bits[0]
    values["high_vibration_alarm"] = alarms.bits[1]
    values["low_pressure_alarm"] = alarms.bits[2]
    return values


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "read"
    client = ModbusTcpClient(HOST, port=PORT)
    client.connect()

    if command == "start":
        client.write_coil(address=0, value=True, slave=1)
        if len(sys.argv) > 2:
            client.write_register(address=0, value=int(sys.argv[2]), slave=1)
        print("Engine start command sent.")
    elif command == "stop":
        client.write_coil(address=0, value=False, slave=1)
        print("Engine stop command sent.")
    elif command == "read":
        try:
            while True:
                values = read_sensors(client)
                print(", ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in values.items()))
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        print(f"Unknown command: {command}")

    client.close()


if __name__ == "__main__":
    main()
