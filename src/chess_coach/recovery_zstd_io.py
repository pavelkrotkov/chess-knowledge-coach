"""Read and write bounded chunks for a native recovery codec."""

import os

CHUNK = 64 * 1024


def read_input(selector, pipe, source, state, expected):
    if not state["pending"]:
        chunk = source.read(CHUNK)
        if not chunk:
            selector.unregister(pipe)
            pipe.close()
            return
        state["input"] += len(chunk)
        if state["input"] > expected:
            raise ValueError("codec input exceeds expected size")
        state["input_hash"].update(chunk)
        state["pending"] = chunk
    try:
        written = os.write(pipe.fileno(), state["pending"])
    except BlockingIOError:
        return
    state["pending"] = state["pending"][written:]


def write_output(selector, pipe, target, state, limit):
    try:
        chunk = os.read(pipe.fileno(), CHUNK)
    except BlockingIOError:
        return
    if not chunk:
        selector.unregister(pipe)
        pipe.close()
        return
    state["output"] += len(chunk)
    if state["output"] > limit:
        raise ValueError("codec output exceeds reserved size")
    if target.write(chunk) != len(chunk):
        raise OSError("codec output write incomplete")
    state["output_hash"].update(chunk)
