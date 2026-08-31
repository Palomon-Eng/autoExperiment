"""
Polls Aranet4 units using aranetctl --scan.
Uses the BLE scheduler to coordinate with M5Stick.
"""

from __future__ import annotations

import asyncio
import logging
import time
import random
import re

import config
from devices.ble_scheduler import scheduler
from bus import bus
from data_logger import logger as data_logger

log = logging.getLogger("aranet4")


class AranetReader:
    def __init__(self, key: str, mac: str, label: str) -> None:
        self.key = key
        self.mac = mac
        self.label = label
        self._last_ok: float = 0.0
        self._consecutive_failures = 0
        self._jitter = random.uniform(0, 2.0)

    @property
    def online(self) -> bool:
        return (time.monotonic() - self._last_ok) < (config.ARANET4_POLL_SECONDS * 3)

    def _parse_scan_output(self, output: str) -> dict:
        """Parse aranetctl --scan output for a specific device."""
        sections = re.split(r'={3,}', output)
        
        for section in sections:
            if self.mac not in section:
                continue
            
            data = {}
            patterns = {
                'co2': r'CO2:\s+(\d+)\s+ppm',
                'temperature': r'Temperature:\s+([\d.]+)\s+°C',
                'humidity': r'Humidity:\s+(\d+)\s+%',
                'pressure': r'Pressure:\s+([\d.]+)\s+hPa',
                'battery': r'Battery:\s+(\d+)\s+%',
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, section)
                if match:
                    if key in ('temperature', 'pressure'):
                        data[key] = float(match.group(1))
                    else:
                        data[key] = int(match.group(1))
            
            return data
        return {}

    async def _wait_for_slot(self) -> bool:
        """Wait until Aranet4 slot is available."""
        max_wait = 30  # Maximum wait time
        waited = 0
        while waited < max_wait:
            if await scheduler.get_aranet_slot():
                return True
            await asyncio.sleep(0.5)
            waited += 0.5
        return False

    async def _read_once(self) -> dict:
        """Run aranetctl --scan and parse the output."""
        # Wait for our time slot
        if not await self._wait_for_slot():
            raise RuntimeError("Could not acquire BLE time slot (timeout)")
        
        try:
            cmd = ["aranetctl", "--scan"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=config.ARANET4_READ_TIMEOUT_SECONDS
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"aranetctl scan failed: {error_msg}")
            
            output = stdout.decode()
            data = self._parse_scan_output(output)
            
            if not data:
                raise RuntimeError(f"Device {self.mac} not found in scan output")
            
            return data
            
        except asyncio.TimeoutError:
            raise TimeoutError("aranetctl scan timed out")
        except Exception as e:
            raise RuntimeError(f"aranetctl error: {e}")

    async def _read_with_retries(self) -> dict:
        last_exc = None
        for attempt in range(1, config.ARANET4_READ_RETRIES + 1):
            try:
                return await asyncio.wait_for(
                    self._read_once(), 
                    timeout=config.ARANET4_READ_TIMEOUT_SECONDS + 5
                )
            except asyncio.TimeoutError:
                last_exc = TimeoutError("read timed out")
                log.warning(
                    "%s (%s) scan attempt %d/%d timed out",
                    self.label, self.mac, attempt, config.ARANET4_READ_RETRIES,
                )
            except Exception as exc:
                last_exc = exc
                log.warning(
                    "%s (%s) scan attempt %d/%d failed: %s",
                    self.label, self.mac, attempt, config.ARANET4_READ_RETRIES,
                    str(exc),
                )
            
            if attempt < config.ARANET4_READ_RETRIES:
                await asyncio.sleep(config.ARANET4_RETRY_BACKOFF_SECONDS)
        
        raise last_exc

    async def run_forever(self) -> None:
        await asyncio.sleep(self._jitter)
        was_online = False
        
        while True:
            try:
                data = await self._read_with_retries()
                self._last_ok = time.monotonic()
                self._consecutive_failures = 0

                fields = {
                    "co2": data.get("co2", 0),
                    "temperature": data.get("temperature", 0),
                    "humidity": data.get("humidity", 0),
                    "pressure": data.get("pressure", 0),
                    "battery": data.get("battery", 0),
                }
                units = {"co2": "ppm", "temperature": "C", "humidity": "%RH", "pressure": "hPa", "battery": "%"}
                
                for field, value in fields.items():
                    if value is not None and value > 0:
                        data_logger.record(self.key, field, value, units[field])

                bus.publish({"type": "reading", "source": self.key, "fields": fields})

                if not was_online:
                    was_online = True
                    bus.publish({"type": "device_status", "source": self.key, "state": "connected"})
                    log.info("%s (%s) connected: CO2=%d, T=%.1f°C, H=%d%%", 
                            self.label, self.mac, fields["co2"], fields["temperature"], fields["humidity"])

            except asyncio.CancelledError:
                log.info("%s (%s) cancelled", self.label, self.mac)
                break
            except Exception as exc:
                self._consecutive_failures += 1
                log.warning("%s (%s) scan failed: %s", self.label, self.mac, str(exc))
                
                if was_online:
                    was_online = False
                    bus.publish({"type": "device_status", "source": self.key, "state": "disconnected"})
                
                if self._consecutive_failures > 3:
                    await asyncio.sleep(min(30, self._consecutive_failures * 5))
            
            # Wait 60 seconds between scans
            await asyncio.sleep(config.ARANET4_POLL_SECONDS)


def build_readers() -> list[AranetReader]:
    return [
        AranetReader(key=key, mac=info["mac"], label=info["label"])
        for key, info in config.ARANET4_DEVICES.items()
    ]
