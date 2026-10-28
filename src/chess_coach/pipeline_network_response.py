"""Read a bounded, uncompressed export response."""

import time


class BudgetExceeded(RuntimeError):
    pass


def bounded_body(response, limit: int, deadline: float) -> bytes:
    if time.monotonic() > deadline:
        raise BudgetExceeded("network response budget exhausted")
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise BudgetExceeded("encoded response cannot be bounded")
    content = bytearray()
    chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
    for chunk in chunks:
        if time.monotonic() > deadline or len(content) + len(chunk) > limit:
            raise BudgetExceeded("network response budget exhausted")
        content.extend(chunk)
    if time.monotonic() > deadline:
        raise BudgetExceeded("network response budget exhausted")
    return bytes(content)


def observe_before_timeout(observe, response) -> None:
    try:
        observe(response)
    except (BudgetExceeded, KeyboardInterrupt):
        while True:
            try:
                observe(response)
                break
            except (BudgetExceeded, KeyboardInterrupt):
                continue
        raise
