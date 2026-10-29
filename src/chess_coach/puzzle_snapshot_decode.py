"""Decode a completed archive with bounded output and verified decoder exit."""

import os
import subprocess
import time
import uuid

from .puzzle_snapshot_decode_stream import decode_stream
from .puzzle_snapshot_state import write_state


def decode(archive, attempt, state, limits, deadline):
    csv = attempt / ("decoded-" + uuid.uuid4().hex + ".csv")
    state.update(phase="decoding", csv_bytes=0)
    write_state(attempt, state)
    process = subprocess.Popen(
        ["zstd", "--decompress", "--stdout", "--quiet", "-M128MB", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        digest = decode_stream(process, csv, attempt, state, limits, deadline)
        remaining = max(0, deadline - time.monotonic())
        if process.wait(timeout=remaining) != 0:
            raise ValueError("archive failed complete zstd decoding")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout:
            process.stdout.close()
    os.chmod(csv, 0o444)
    return csv, digest
