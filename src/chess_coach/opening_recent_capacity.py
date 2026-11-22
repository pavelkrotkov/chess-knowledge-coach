"""Check the current allocated project and filesystem reserve before import."""

import shutil
import subprocess
import time

from .recovery_capacity import PROJECT_LIMIT, RESERVE

WORKING = 128 * 1024 * 1024


def check(root, directory, *, deadline=None):
    remaining = 8 if deadline is None else min(8, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("reference build deadline")
    measured = subprocess.run(
        ["du", "-skx", str(root)], capture_output=True, text=True, check=True, timeout=remaining
    )
    usage = int(measured.stdout.split()[0]) * 1024
    if usage + WORKING + RESERVE > PROJECT_LIMIT:
        raise ValueError("project storage reserve unavailable")
    if shutil.disk_usage(directory).free < WORKING + RESERVE:
        raise ValueError("filesystem storage reserve unavailable")
    return usage
