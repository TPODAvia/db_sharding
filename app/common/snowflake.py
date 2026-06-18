from __future__ import annotations

import threading
import time

class SnowflakeGenerator:
    """
    64-bit Snowflake-like ID:
    41 bits timestamp millis since custom epoch
    10 bits worker_id
    12 bits sequence inside the same millisecond
    """

    def __init__(self, worker_id: int, epoch_millis: int = 1704067200000):
        if not 0 <= worker_id <= 1023:
            raise ValueError("worker_id must be between 0 and 1023")
        self.worker_id = worker_id
        self.epoch_millis = epoch_millis
        self.sequence = 0
        self.last_millis = -1
        self.lock = threading.Lock()

    @staticmethod
    def _now_millis() -> int:
        return int(time.time() * 1000)

    def next_id(self) -> int:
        with self.lock:
            now = self._now_millis()

            if now < self.last_millis:
                raise RuntimeError(
                    f"Clock moved backwards: now={now}, last={self.last_millis}"
                )

            if now == self.last_millis:
                self.sequence = (self.sequence + 1) & 0xFFF
                if self.sequence == 0:
                    while now <= self.last_millis:
                        now = self._now_millis()
            else:
                self.sequence = 0

            self.last_millis = now
            return ((now - self.epoch_millis) << 22) | (self.worker_id << 12) | self.sequence

    def parse(self, value: int) -> dict[str, int]:
        sequence = value & 0xFFF
        worker_id = (value >> 12) & 0x3FF
        timestamp_millis = (value >> 22) + self.epoch_millis
        return {
            "timestamp_millis": timestamp_millis,
            "worker_id": worker_id,
            "sequence": sequence,
        }
