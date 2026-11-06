"""Bound the archive decompressor output and execution time."""

import os
import select
import subprocess
import time

DECODE_LIMIT = 32_000_000
SECONDS = 30


def decode(file):
    deadline = time.monotonic() + SECONDS
    process = subprocess.Popen(
        ["/usr/bin/zstd", "-d", "-c", "--quiet"], stdin=file, stdout=subprocess.PIPE
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
                if process.wait(timeout=max(0.01, deadline - time.monotonic())):
                    raise ValueError("reference archive could not be decoded")
                return bytes(output), False
            output.extend(data)
        return bytes(output[:DECODE_LIMIT]), True
    finally:
        process.kill() if process.poll() is None else None
        process.wait()
        process.stdout.close()
