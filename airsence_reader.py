"""
Polls the AirSENCE Standard's InfluxDB 2.x bucket for its latest readings.
Polled once per minute.
"""

from __future__ import annotations

import asyncio
import logging
import time
import random

from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

import config
from bus import bus
from data_logger import logger as data_logger

log = logging.getLogger("airsence")

SOURCE = "airsence"


class AirsenceReader:
    def __init__(self) -> None:
        self._last_ok: float = 0.0
        self._logged_sample = False
        self._jitter = random.uniform(0, 2.0)

    @property
    def online(self) -> bool:
        return (time.monotonic() - self._last_ok) < (config.AIRSENCE_POLL_SECONDS * 3)

    def _build_flux_query(self) -> str:
        device_filter = ""
        placeholder = "xxxxxxxxxx" in config.AIRSENCE_DEVICE_ID
        if config.AIRSENCE_DEVICE_TAG_KEY and config.AIRSENCE_DEVICE_ID and not placeholder:
            device_filter = (
                f'\n  |> filter(fn: (r) => r["{config.AIRSENCE_DEVICE_TAG_KEY}"] == '
                f'"{config.AIRSENCE_DEVICE_ID}")'
            )
        return (
            f'from(bucket: "{config.AIRSENCE_BUCKET}")'
            f'\n  |> range(start: -{config.AIRSENCE_QUERY_RANGE_MINUTES}m)'
            f'{device_filter}'
            f'\n  |> filter(fn: (r) => r["_measurement"] == "{config.AIRSENCE_MEASUREMENT}")'
            '\n  |> last()'
        )

    async def _read_once(self, client: InfluxDBClientAsync) -> dict:
        tables = await client.query_api().query(self._build_flux_query(), org=config.AIRSENCE_ORG_ID)

        fields: dict = {}
        raw_sample = []
        for table in tables:
            for record in table.records:
                field_name = record.get_field()
                value = record.get_value()
                raw_sample.append(record.values)
                if field_name is None or value is None:
                    continue
                mapped_name, unit = config.AIRSENCE_FIELD_MAP.get(field_name, (field_name, ""))
                fields[mapped_name] = (value, unit)

        if not self._logged_sample:
            self._logged_sample = True
            log.debug("AirSENCE sample query result (raw records): %s", raw_sample)

        return fields

    async def _read_with_retries(self, client: InfluxDBClientAsync) -> dict:
        last_exc: Exception | None = None
        for attempt in range(1, config.AIRSENCE_READ_RETRIES + 1):
            try:
                return await asyncio.wait_for(
                    self._read_once(client), timeout=config.AIRSENCE_READ_TIMEOUT_SECONDS
                )
            except Exception as exc:
                last_exc = exc
                log.warning(
                    "AirSENCE read attempt %d/%d failed: %s",
                    attempt, config.AIRSENCE_READ_RETRIES, exc,
                )
                if attempt < config.AIRSENCE_READ_RETRIES:
                    await asyncio.sleep(config.AIRSENCE_RETRY_BACKOFF_SECONDS)
        raise last_exc

    async def run_forever(self) -> None:
        if not config.AIRSENCE_ENABLED:
            log.info("AirSENCE integration disabled")
            return
        
        await asyncio.sleep(self._jitter)
        
        was_online = False
        async with InfluxDBClientAsync(
            url=config.AIRSENCE_INFLUX_URL,
            token=config.AIRSENCE_API_TOKEN,
            org=config.AIRSENCE_ORG_ID,
        ) as client:
            while True:
                try:
                    fields = await self._read_with_retries(client)
                    self._last_ok = time.monotonic()

                    for field, (value, unit) in fields.items():
                        data_logger.record(SOURCE, field, value, unit)
                    bus.publish({
                        "type": "reading", "source": SOURCE,
                        "fields": {f: v for f, (v, _u) in fields.items()},
                        "units": {f: u for f, (_v, u) in fields.items()},
                    })

                    if not was_online:
                        was_online = True
                        bus.publish({"type": "device_status", "source": SOURCE, "state": "connected"})

                except Exception as exc:
                    log.warning("AirSENCE read failed after retries: %s", exc)
                    if was_online:
                        was_online = False
                        bus.publish({"type": "device_status", "source": SOURCE, "state": "disconnected"})

                jitter = random.uniform(-1.0, 1.0)
                await asyncio.sleep(max(1.0, config.AIRSENCE_POLL_SECONDS + jitter))


# THIS LINE IS CRITICAL - creates the instance that main.py imports
airsence = AirsenceReader()
