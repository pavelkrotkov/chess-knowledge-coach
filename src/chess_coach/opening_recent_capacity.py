"""Check the current allocated project and filesystem reserve before import."""

import shutil
import subprocess

from .recovery_capacity import PROJECT_LIMIT, RESERVE

WORKING = 128 * 1024 * 1024


def check(root, directory):
    measured = subprocess.run(
        ["du", "-skx", str(root)], capture_output=True, text=True, check=True, timeout=8
    )
    usage = int(measured.stdout.split()[0]) * 1024
    if usage + WORKING + RESERVE > PROJECT_LIMIT:
        raise ValueError("project storage reserve unavailable")
    if shutil.disk_usage(directory).free < WORKING + RESERVE:
        raise ValueError("filesystem storage reserve unavailable")
    return usage
