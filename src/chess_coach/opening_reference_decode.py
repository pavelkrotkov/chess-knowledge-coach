"""Bound the archive decompressor output and execution time."""

import os
import select
import subprocess
import time

from .opening_reference_decode_end import bounded_deadline, finish

DECODE_LIMIT = 32_000_000
SECONDS = 30


def decode(file, *, allow_partial=False, deadline=None):
    deadline = bounded_deadline(SECONDS, deadline)
    process = subprocess.Popen(
        ["/usr/bin/zstd", "-d", "-c", "--quiet"],
        stdin=file,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "LC_ALL": "C"},
    )
    assert process.stdout is not None
    output = bytearray()
    try:
        while len(output) <= DECODE_LIMIT:
            wait = deadline - time.monotonic()
            if wait <= 0 or not select.select([process.stdout], [], [], wait)[0]:
                raise ValueError("reference decoding deadline exceeded")
            data = os.read(process.stdout.fileno(), min(65536, DECODE_LIMIT + 1 - len(output)))
            if not data:
                return bytes(output), finish(process, deadline, allow_partial)
            output.extend(data)
        return bytes(output[:DECODE_LIMIT]), True
    finally:
        process.kill() if process.poll() is None else None
        process.wait()
        process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
