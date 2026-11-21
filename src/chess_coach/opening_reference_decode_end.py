"""Accept only a confirmed partial-frame EOF from the bounded decoder."""

import time


def finish(process, deadline, allow_partial):
    status = process.wait(timeout=max(0.01, deadline - time.monotonic()))
    if not status:
        return False
    assert process.stderr is not None
    lines = process.stderr.read(4096).splitlines()
    if (
        allow_partial
        and len(lines) == 1
        and lines[0].rstrip().endswith(b"Read error (39) : premature end")
    ):
        return True
    raise ValueError("reference archive could not be decoded")
