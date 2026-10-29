"""Enforce time, size, and remaining disk limits."""

import shutil
import time


def check_budget(path, limits, deadline, amount, maximum, write_bytes=0):
    if time.monotonic() >= deadline:
        raise TimeoutError("snapshot time limit reached")
    if amount > maximum:
        raise ValueError("snapshot byte limit exceeded")
    if shutil.disk_usage(path).free < limits.reserve_bytes + write_bytes:
        raise OSError("snapshot disk reserve breached")
