"""
Central configuration for the reactor control console.
All sensors polled once per minute.
"""

# ---------------------------------------------------------------------------
# Arduino Uno R3 (relay / pump / valve controller ONLY)
# ---------------------------------------------------------------------------
ARDUINO_SERIAL_PORT = "/dev/ttyACM0"
ARDUINO_BAUD_RATE = 115200
ARDUINO_RECONNECT_SECONDS = 5

# ---------------------------------------------------------------------------
# M5StickC Plus2 (BLE advertising broadcaster running SEN55)
# ---------------------------------------------------------------------------
M5STICK_BLE_NAME = "M5Stick_SEN55"
M5STICK_MANUFACTURER_ID = 0xFFFF
M5STICK_TIMEOUT_SECONDS = 15

# ---------------------------------------------------------------------------
# Aranet4 CO2 monitors - Polled every 60 seconds
# ---------------------------------------------------------------------------
ARANET4_DEVICES = {
    "aranet_1": {"mac": "D0:54:AF:9D:F3:0E", "label": "Aranet 4 - Intake"},
    "aranet_2": {"mac": "F5:74:FE:6C:CB:CC", "label": "Aranet 4 - Chamber"},
}
ARANET4_POLL_SECONDS = 60  # Once per minute
ARANET4_READ_RETRIES = 2
ARANET4_RETRY_BACKOFF_SECONDS = 2
ARANET4_READ_TIMEOUT_SECONDS = 15
ARANET4_LOCK_TIMEOUT_SECONDS = 30
BLE_PAUSE_RESUME_TIMEOUT_SECONDS = 5
BLE_SETTLE_SECONDS = 0.3

# ---------------------------------------------------------------------------
# AirSENCE Standard - Polled every 60 seconds
# ---------------------------------------------------------------------------
AIRSENCE_ENABLED = True
AIRSENCE_INFLUX_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
AIRSENCE_API_TOKEN = "XL977xmZp-CJFJ_dfqROTS561PL6WAYYchogSkQp8nr9nU1fGmoLqreEtIA6kPnDsNO62rqFC4AXPTEmVQcLLA=="
AIRSENCE_ORG_ID = "7d09b07ae81cf7af"
AIRSENCE_BUCKET = "H2020"
AIRSENCE_DEVICE_ID = "AirSENCE-0521C6E740164"
AIRSENCE_DEVICE_TAG_KEY = "DeviceID"
AIRSENCE_MEASUREMENT = "Pollutant"
AIRSENCE_POLL_SECONDS = 60  # Once per minute
AIRSENCE_QUERY_RANGE_MINUTES = 10
AIRSENCE_READ_RETRIES = 2
AIRSENCE_RETRY_BACKOFF_SECONDS = 5
AIRSENCE_READ_TIMEOUT_SECONDS = 15

AIRSENCE_FIELD_MAP = {
    "NO2": ("no2", "ppb"),
    "NO": ("no", "ppb"),
    "CO": ("co", "ppm"),
    "O3": ("o3", "ppb"),
    "SO2": ("so2", "ppb"),
    "CO2": ("co2", "ppm"),
    "H2S": ("h2s", "ppb"),
    "NH3": ("nh3", "ppb"),
    "CH4": ("ch4", "ppm"),
    "PM1": ("pm1", "ug/m3"),
    "PM2.5": ("pm25", "ug/m3"),
    "PM10": ("pm10", "ug/m3"),
    "Temperature": ("temperature", "C"),
    "Humidity": ("humidity", "%RH"),
}

# ---------------------------------------------------------------------------
# Web server / data logging
# ---------------------------------------------------------------------------
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8000
DATA_LOG_DIR = "logs"
CSV_FLUSH_SECONDS = 60
LIVE_HISTORY_POINTS = 300
