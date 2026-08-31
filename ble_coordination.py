"""
Serializes BLE operations on the Pi's single Bluetooth radio.
"""

from __future__ import annotations

import asyncio

ble_lock = asyncio.Lock()
