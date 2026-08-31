"""
Listens for the M5StickC Plus2's BLE advertisements.
Uses the BLE scheduler to coordinate with Aranet4 scans.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

import config
from bus import bus
from data_logger import logger as data_logger
from devices.ble_scheduler import scheduler

log = logging.getLogger("m5stick")

SOURCE = "m5stick"
_STRUCT_FMT = "<4f"


class M5StickListener:
    def __init__(self) -> None:
        self._last_seen: float = 0.0
        self._was_online = False
        self._scanner: BleakScanner | None = None
        self._scanning = False
        self._state_lock = asyncio.Lock()
        self._reconnect_delay = 5

    @property
    def online(self) -> bool:
        return (time.monotonic() - self._last_seen) < config.M5STICK_TIMEOUT_SECONDS

    def _on_detection(self, device: BLEDevice, adv: AdvertisementData) -> None:
        if device.name != config.M5STICK_BLE_NAME and config.M5STICK_MANUFACTURER_ID not in adv.manufacturer_data:
            return
        payload = adv.manufacturer_data.get(config.M5STICK_MANUFACTURER_ID)
        if payload is None or len(payload) < struct.calcsize(_STRUCT_FMT):
            return

        temp, hum, nox, pm25 = struct.unpack(_STRUCT_FMT, payload[: struct.calcsize(_STRUCT_FMT)])
        self._last_seen = time.monotonic()

        data_logger.record(SOURCE, "temperature", temp, "C")
        data_logger.record(SOURCE, "humidity", hum, "%RH")
        data_logger.record(SOURCE, "nox", nox, "index")
        data_logger.record(SOURCE, "pm25", pm25, "ug/m3")
        bus.publish({
            "type": "reading", "source": SOURCE,
            "fields": {"temperature": temp, "humidity": hum, "nox": nox, "pm25": pm25},
        })

    async def _scan_loop(self) -> None:
        """Internal scan loop that runs only during M5Stick time slots."""
        while True:
            # Check if we have permission to scan
            if not await scheduler.get_m5stick_slot():
                # Not our slot, wait and check again
                await asyncio.sleep(1)
                continue
            
            try:
                if self._scanner is None:
                    self._scanner = BleakScanner(detection_callback=self._on_detection)
                
                if not self._scanning:
                    try:
                        await asyncio.wait_for(self._scanner.start(), timeout=5.0)
                        self._scanning = True
                        log.debug("M5Stick scanner started (slot)")
                    except asyncio.TimeoutError:
                        log.warning("M5Stick start timeout")
                        continue
                
                # Scan for a short period, then check again
                await asyncio.sleep(1)
                
                # If we're still in the slot, continue scanning
                if not await scheduler.get_m5stick_slot():
                    # Slot expired, stop scanning
                    await self.pause()
                    log.debug("M5Stick slot ended")
                    await asyncio.sleep(1)
                
            except Exception as exc:
                log.warning("M5Stick scan error: %s", exc)
                try:
                    if self._scanner:
                        await self._scanner.stop()
                except Exception:
                    pass
                self._scanning = False
                await asyncio.sleep(1)

    async def pause(self) -> None:
        """Stop scanning."""
        async with self._state_lock:
            if self._scanner is not None and self._scanning:
                try:
                    await asyncio.wait_for(self._scanner.stop(), timeout=config.BLE_PAUSE_RESUME_TIMEOUT_SECONDS)
                    self._scanning = False
                    log.debug("M5Stick scanner paused")
                except Exception:
                    pass

    async def run_forever(self) -> None:
        """Main entry point - runs the scan loop."""
        while True:
            try:
                await self._scan_loop()
            except asyncio.CancelledError:
                log.info("M5Stick scanner cancelled")
                break
            except Exception as exc:
                log.warning("M5Stick scan loop error: %s", exc)
                await asyncio.sleep(self._reconnect_delay)


m5stick = M5StickListener()
