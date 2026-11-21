"""Move bounded chunks through a native codec without pipe deadlocks."""

import hashlib

from .recovery_zstd_io import read_input, write_output


def pump(selector, source, target, expected, limit, guard, deadline, restoring):
    state = {
        "input": 0,
        "output": 0,
        "pending": b"",
        "input_hash": hashlib.sha256(),
        "output_hash": hashlib.sha256(),
    }
    while selector.get_map():
        deadline.check()
        remaining = max(0, limit - state["output"]) if restoring else expected
        guard.check(remaining)
        for key, _ in selector.select(timeout=0.2):
            if key.data == "input":
                read_input(selector, key.fileobj, source, state, expected)
            else:
                write_output(selector, key.fileobj, target, state, limit)
    if state["input"] != expected:
        raise ValueError("codec input size differs")
    return {
        "input_bytes": state["input"],
        "output_bytes": state["output"],
        "input_sha256": state["input_hash"].hexdigest(),
        "output_sha256": state["output_hash"].hexdigest(),
    }
