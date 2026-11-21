"""Run bounded native Zstandard metadata commands."""

import re
import subprocess
import time

from .recovery_zstd_process import PREFIX


def run(arguments, deadline):
    remaining = deadline.end - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("database snapshot time limit exceeded")
    try:
        result = subprocess.run(
            [*PREFIX, *arguments],
            capture_output=True,
            timeout=min(30, remaining),
            env={"LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("Zstandard codec unavailable or timed out") from None
    deadline.check()
    if result.returncode or len(result.stdout) > 8192 or len(result.stderr) > 8192:
        raise ValueError("Zstandard frame unavailable or invalid")
    return result.stdout.decode("ascii", errors="strict")


def version(deadline):
    text = run(["--version"], deadline)
    match = re.search(r"\bv(\d+\.\d+\.\d+)\b", text)
    if not match:
        raise ValueError("Zstandard codec version unavailable")
    return match.group(1)
