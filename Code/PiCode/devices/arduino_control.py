"""
Talks to the Arduino Uno R3 over USB serial.
"""

from __future__ import annotations

import asyncio
import logging

import serial_asyncio

import config
from bus import bus
from data_logger import logger as data_logger

log = logging.getLogger("arduino")

SOURCE = "arduino"


class ArduinoController:
    def __init__(self) -> None:
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def run_forever(self) -> None:
        while True:
            try:
                reader, writer = await serial_asyncio.open_serial_connection(
                    url=config.ARDUINO_SERIAL_PORT, baudrate=config.ARDUINO_BAUD_RATE
                )
                self._writer = writer
                self._connected = True
                self._announce_status("connected")
                log.info("Arduino connected on %s", config.ARDUINO_SERIAL_PORT)

                while True:
                    raw = await reader.readline()
                    if not raw:
                        break
                    line = raw.decode(errors="ignore").strip()
                    if line:
                        self._handle_line(line)

            except (OSError, serial_asyncio.serial.SerialException) as exc:
                log.warning("Arduino serial error: %s", exc)
            finally:
                self._connected = False
                self._writer = None
                self._announce_status("disconnected")
                await asyncio.sleep(config.ARDUINO_RECONNECT_SECONDS)

    def _announce_status(self, connection_state: str) -> None:
        bus.publish({"type": "device_status", "source": SOURCE, "state": connection_state})

    def _handle_line(self, line: str) -> None:
        if line.startswith("DATA,"):
            return

        data_logger.record(SOURCE, "status", line, "")
        bus.publish({"type": "log", "source": SOURCE, "message": line})

    async def _send(self, char: str) -> bool:
        if not self._writer:
            return False
        self._writer.write(char.encode())
        await self._writer.drain()
        return True

    async def start(self) -> bool:
        return await self._send("1")

    async def stop(self) -> bool:
        return await self._send("0")

    async def pump_test(self) -> bool:
        return await self._send("t")

    async def start_sequence(self) -> bool:
        return await self._send("f")

    async def leak_test(self) -> bool:
        return await self._send("l")

    async def unfreeze(self) -> bool:
        return await self._send(" ")

    async def pulse_valve1(self) -> bool:
        return await self._send("2")

    async def pulse_valve2(self) -> bool:
        return await self._send("3")

    async def pulse_valve3(self) -> bool:
        return await self._send("4")

    async def pulse_pump(self) -> bool:
        return await self._send("5")


arduino = ArduinoController()
