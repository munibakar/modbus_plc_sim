"""Modbus TCP server that simulates a real PLC monitoring an engine.

Register / bit map (all addresses zero-based, zero_mode=True):

  Coils            (FC01 read / FC05 write) - operator controls
    0: Engine start/stop command (write 1 to start, 0 to stop)

  Discrete Inputs  (FC02 read-only)         - alarm status
    0: High temperature alarm
    1: High vibration alarm
    2: Low pressure alarm

  Input Registers  (FC04 read-only)         - live sensor data, 32-bit
                                               float, 2 registers each,
                                               big-endian byte/word order
    0-1:  Temperature (deg C)
    2-3:  Pressure (bar)
    4-5:  Vibration (mm/s)
    6-7:  Humidity (%RH)
    8-9:  RPM
    10-11: Runtime (hours)

  Holding Registers (FC03 read / FC06,16 write) - setpoints
    0: Target RPM (uint16, 0-3200)
"""

from __future__ import annotations

import asyncio
import logging

from pymodbus.constants import Endian
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.server import StartAsyncTcpServer

from engine import VirtualEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("modbus_plc_sim")

HOST = "0.0.0.0"
PORT = 5020
UPDATE_INTERVAL = 1.0  # seconds between simulated PLC scans

COIL_ENGINE_RUN = 0
DI_HIGH_TEMP_ALARM = 0
DI_HIGH_VIBRATION_ALARM = 1
DI_LOW_PRESSURE_ALARM = 2
IR_SENSOR_BASE = 0  # 6 floats -> 12 registers
HR_TARGET_RPM = 0


def build_context() -> ModbusServerContext:
    di_block = ModbusSequentialDataBlock(0, [0] * 3)
    co_block = ModbusSequentialDataBlock(0, [0])
    ir_block = ModbusSequentialDataBlock(0, [0] * 12)
    hr_block = ModbusSequentialDataBlock(0, [1800])  # default target RPM setpoint

    slave = ModbusSlaveContext(di=di_block, co=co_block, ir=ir_block, hr=hr_block, zero_mode=True)
    return ModbusServerContext(slaves=slave, single=True)


def build_identity() -> ModbusDeviceIdentification:
    identity = ModbusDeviceIdentification()
    identity.VendorName = "Virtual Automation Co."
    identity.ProductCode = "VPLC-ENGINE"
    identity.VendorUrl = "https://example.invalid"
    identity.ProductName = "Virtual PLC - Engine Monitor"
    identity.ModelName = "VPLC-100"
    identity.MajorMinorRevision = "1.0"
    return identity


async def updater_task(context: ModbusServerContext, engine: VirtualEngine) -> None:
    """Simulate one PLC scan cycle: read commands, advance the engine
    model, and publish fresh sensor values into the datastore."""
    store = context[0]
    while True:
        await asyncio.sleep(UPDATE_INTERVAL)

        run_command = store.getValues(1, COIL_ENGINE_RUN, count=1)[0]
        engine.start() if run_command else engine.stop()

        target_rpm = store.getValues(3, HR_TARGET_RPM, count=1)[0]
        engine.set_target_rpm(target_rpm)

        engine.tick(UPDATE_INTERVAL)

        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        for value in (
            engine.temperature,
            engine.pressure,
            engine.vibration,
            engine.humidity,
            engine.rpm,
            engine.runtime_hours,
        ):
            builder.add_32bit_float(value)
        store.setValues(4, IR_SENSOR_BASE, builder.to_registers())

        store.setValues(
            2,
            DI_HIGH_TEMP_ALARM,
            [
                engine.high_temperature_alarm,
                engine.high_vibration_alarm,
                engine.low_pressure_alarm,
            ],
        )

        log.info(
            "running=%s rpm=%.0f temp=%.1fC pressure=%.2fbar vibration=%.2fmm/s humidity=%.1f%%",
            engine.running,
            engine.rpm,
            engine.temperature,
            engine.pressure,
            engine.vibration,
            engine.humidity,
        )


async def main() -> None:
    context = build_context()
    identity = build_identity()
    engine = VirtualEngine()

    asyncio.create_task(updater_task(context, engine))

    log.info("Starting virtual PLC Modbus TCP server on %s:%s", HOST, PORT)
    await StartAsyncTcpServer(context=context, identity=identity, address=(HOST, PORT))


if __name__ == "__main__":
    asyncio.run(main())
