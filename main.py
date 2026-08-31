"""
Reactor Console - entry point.
All sensors polled once per minute.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from bus import bus
from data_logger import logger as data_logger
from devices.arduino_control import arduino
from devices.aranet_reader import build_readers
from devices.m5stick_ble import m5stick
from devices.airsence_reader import airsence

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")

_shutdown_event = asyncio.Event()
_device_tasks = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of background tasks."""
    global _device_tasks
    
    log.info("Starting Reactor Console (1-minute poll cycle)...")
    
    _device_tasks = [
        asyncio.create_task(_csv_flush_loop()),
    ]
    
    # Start Arduino first (serial, no BLE)
    _device_tasks.append(asyncio.create_task(arduino.run_forever()))
    await asyncio.sleep(0.5)
    
    # Start M5Stick scanner (BLE scanner)
    _device_tasks.append(asyncio.create_task(m5stick.run_forever()))
    await asyncio.sleep(1.0)
    
    # Start Aranet4 readers with staggered startup
    readers = build_readers()
    for i, reader in enumerate(readers):
        await asyncio.sleep(0.5 + (i * 0.5))
        _device_tasks.append(asyncio.create_task(reader.run_forever()))
    
    # Start AirSENCE (HTTP/cloud, no BLE)
    await asyncio.sleep(0.5)
    _device_tasks.append(asyncio.create_task(airsence.run_forever()))
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))
    
    log.info("All device tasks launched; logging to %s", data_logger.csv_path())
    
    yield
    
    await _shutdown()


async def _shutdown():
    """Gracefully shutdown all background tasks."""
    log.info("Shutting down...")
    _shutdown_event.set()
    
    for task in _device_tasks:
        if not task.done():
            task.cancel()
    
    if _device_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*_device_tasks, return_exceptions=True), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning("Some tasks didn't shut down cleanly")
    
    log.info("Shutdown complete")


app = FastAPI(title="Reactor Console", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


async def _csv_flush_loop() -> None:
    """Writes buffered sensor readings to disk once per minute."""
    while not _shutdown_event.is_set():
        try:
            await asyncio.sleep(config.CSV_FLUSH_SECONDS)
            if not _shutdown_event.is_set():
                data_logger.flush_numeric_to_csv()
                log.debug("CSV flush completed")
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("Error in CSV flush loop: %s", e)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    with open("static/index.html") as f:
        return HTMLResponse(f.read())


@app.get("/api/snapshot")
async def snapshot() -> JSONResponse:
    """Latest value of every field, for a client that just connected."""
    return JSONResponse({
        "readings": data_logger.latest_snapshot(),
        "devices": {
            "arduino": arduino.connected,
            "m5stick": m5stick.online,
            **{r.key: r.online for r in build_readers()},
            "airsence": airsence.online,
        },
        "row_count": data_logger.row_count(),
    })


@app.get("/api/history/{source}/{field}")
async def history(source: str, field: str) -> JSONResponse:
    return JSONResponse(data_logger.history(source, field))


@app.get("/api/csv")
async def download_csv() -> FileResponse:
    return FileResponse(
        data_logger.csv_path(),
        media_type="text/csv",
        filename="reactor_data_log.csv",
    )


# --- Arduino control endpoints ---------------------------------------------
_ARDUINO_ACTIONS = {
    "start": arduino.start,
    "stop": arduino.stop,
    "pump_test": arduino.pump_test,
    "start_sequence": arduino.start_sequence,
    "leak_test": arduino.leak_test,
    "unfreeze": arduino.unfreeze,
    "pulse_valve1": arduino.pulse_valve1,
    "pulse_valve2": arduino.pulse_valve2,
    "pulse_valve3": arduino.pulse_valve3,
    "pulse_pump": arduino.pulse_pump,
}


@app.post("/api/arduino/{action}")
async def arduino_action(action: str) -> JSONResponse:
    fn = _ARDUINO_ACTIONS.get(action)
    if fn is None:
        return JSONResponse({"ok": False, "error": f"unknown action '{action}'"}, status_code=404)
    if not arduino.connected:
        return JSONResponse({"ok": False, "error": "Arduino not connected"}, status_code=503)
    ok = await fn()
    return JSONResponse({"ok": ok})


# --- Live websocket ----------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)
