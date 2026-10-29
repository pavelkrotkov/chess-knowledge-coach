"""Validate UTF-8 while streaming bounded decoded output."""

import codecs
import hashlib
import os
import select
import time

from .puzzle_snapshot_budget import check_budget
from .puzzle_snapshot_state import write_state


def decode_stream(process, csv, attempt, state, limits, deadline):
    digest = hashlib.sha256()
    utf8 = codecs.getincrementaldecoder("utf-8")("strict")
    with csv.open("xb") as out:
        while True:
            check_budget(attempt, limits, deadline, state["csv_bytes"], limits.max_csv_bytes)
            ready, _, _ = select.select(
                [process.stdout], [], [], max(0, deadline - time.monotonic())
            )
            if not ready:
                raise TimeoutError("snapshot decoding time limit reached")
            chunk = os.read(process.stdout.fileno(), 1024 * 1024)
            if not chunk:
                break
            size = state["csv_bytes"] + len(chunk)
            check_budget(attempt, limits, deadline, size, limits.max_csv_bytes, len(chunk))
            utf8.decode(chunk)
            out.write(chunk)
            digest.update(chunk)
            state["csv_bytes"] = size
            write_state(attempt, state)
        utf8.decode(b"", final=True)
        out.flush()
        os.fsync(out.fileno())
    return digest.hexdigest()
