"""Explicit limits for snapshot transfer and decoding."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_archive_bytes: int
    max_csv_bytes: int
    reserve_bytes: int
    seconds: float
    connect_timeout: float
    read_timeout: float

    def validate(self):
        if (
            min(
                self.max_archive_bytes,
                self.max_csv_bytes,
                self.seconds,
                self.connect_timeout,
                self.read_timeout,
            )
            <= 0
        ):
            raise ValueError("byte and time limits must be positive")
        if not all(
            math.isfinite(value)
            for value in (self.seconds, self.connect_timeout, self.read_timeout)
        ):
            raise ValueError("time limits must be finite")
        if self.reserve_bytes < 0:
            raise ValueError("disk reserve cannot be negative")
