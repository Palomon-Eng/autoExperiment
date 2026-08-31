"""
BLE Time-slot coordinator.
Simple time-based alternation between M5Stick and Aranet4.
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger("ble_scheduler")

# Time slots in seconds
M5STICK_SLOT = 30
ARANET4_SLOT = 30
CYCLE_TIME = M5STICK_SLOT + ARANET4_SLOT  # 60 seconds total

class BLEScheduler:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._cycle_start = time.monotonic()
        log.info("BLE Scheduler initialized: M5Stick=%ds, Aranet4=%ds, Cycle=%ds", 
                 M5STICK_SLOT, ARANET4_SLOT, CYCLE_TIME)

    def _get_current_slot(self) -> str:
        """Determine current slot based on time."""
        elapsed = time.monotonic() - self._cycle_start
        cycle_position = elapsed % CYCLE_TIME
        
        if cycle_position < M5STICK_SLOT:
            return "m5stick"
        else:
            return "aranet"

    async def get_m5stick_slot(self) -> bool:
        """Check if M5Stick can scan now."""
        async with self._lock:
            slot = self._get_current_slot()
            return slot == "m5stick"

    async def get_aranet_slot(self) -> bool:
        """Check if Aranet4 can scan now."""
        async with self._lock:
            slot = self._get_current_slot()
            return slot == "aranet"

scheduler = BLEScheduler()
