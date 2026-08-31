"""
Unified data logging.
"""

from __future__ import annotations

import csv
import os
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Tuple

import config

_CSV_HEADER = ["timestamp_iso", "source", "field", "value", "unit"]


class DataLogger:
    def __init__(self, log_dir: str = config.DATA_LOG_DIR, history_len: int = config.LIVE_HISTORY_POINTS):
        os.makedirs(log_dir, exist_ok=True)
        run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = os.path.join(log_dir, f"reactor_data_log_{run_stamp}.csv")
        self._lock = threading.Lock()
        self._history_len = history_len
        self._live: Dict[str, Dict[str, Deque[Tuple[str, float]]]] = defaultdict(lambda: defaultdict(
            lambda: deque(maxlen=self._history_len)
        ))
        self._latest: Dict[str, Dict[str, dict]] = defaultdict(dict)
        with open(self._path, "w", newline="") as f:
            csv.writer(f).writerow(_CSV_HEADER)

    def _write_row(self, ts: str, source: str, field: str, value, unit: str) -> None:
        with open(self._path, "a", newline="") as f:
            csv.writer(f).writerow([ts, source, field, value, unit])

    def record(self, source: str, field: str, value, unit: str = "") -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            if isinstance(value, (int, float)):
                self._live[source][field].append((ts, value))
                self._latest[source][field] = {"timestamp": ts, "value": value, "unit": unit}
            else:
                self._latest[source][field] = {"timestamp": ts, "value": value, "unit": unit}
                self._write_row(ts, source, field, value, unit)

    def flush_numeric_to_csv(self) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            for source, fields in self._latest.items():
                for field, info in fields.items():
                    if isinstance(info["value"], (int, float)):
                        self._write_row(ts, source, field, info["value"], info.get("unit", ""))

    def latest_snapshot(self) -> dict:
        with self._lock:
            return {
                source: dict(fields) for source, fields in self._latest.items()
            }

    def history(self, source: str, field: str) -> List[dict]:
        with self._lock:
            return [{"timestamp": t, "value": v} for t, v in self._live[source][field]]

    def csv_path(self) -> str:
        return self._path

    def row_count(self) -> int:
        with self._lock:
            try:
                with open(self._path, "r") as f:
                    return max(sum(1 for _ in f) - 1, 0)
            except FileNotFoundError:
                return 0


logger = DataLogger()
