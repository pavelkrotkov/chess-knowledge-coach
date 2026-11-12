"""Stream one native search with the original whole-search time limit."""

import asyncio
import time
from concurrent.futures import TimeoutError

from .purpose_config import FINAL_SECONDS
from .purpose_deadline import CLEANUP_RESERVE
from .purpose_iteration import Iterations


async def _consume(protocol, board, position, limit, roots):
    state = Iterations(board, position, roots)
    with await protocol.analysis(board, limit, multipv=2, root_moves=roots) as stream:
        async for info in stream:
            state.add(info)
    return state


def search(engine, board, position, limit, roots, deadline):
    remaining = deadline - time.monotonic() - CLEANUP_RESERVE
    if remaining <= 0:
        return None, "worker_deadline"
    timeout = min(remaining, engine.timeout + FINAL_SECONDS)
    coroutine = asyncio.wait_for(_consume(engine.protocol, board, position, limit, roots), timeout)
    future = asyncio.run_coroutine_threadsafe(coroutine, engine.protocol.loop)
    try:
        return future.result(timeout=timeout), None
    except TimeoutError:
        future.cancel()
        return (
            None,
            "worker_deadline" if remaining <= engine.timeout + FINAL_SECONDS else "engine_timeout",
        )
    except Exception:
        return None, "engine_failure"
