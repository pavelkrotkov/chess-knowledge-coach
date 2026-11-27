"""Stream one native search with the original whole-search time limit."""

import asyncio
import time
from concurrent.futures import TimeoutError

from .opening_measure_reference import ReferenceIterations
from .purpose_config import FINAL_SECONDS
from .purpose_deadline import CLEANUP_RESERVE
from .purpose_iteration import Iterations


async def _consume(protocol, board, position, limit, roots, bounds, reference, game):
    state = (ReferenceIterations if reference else Iterations)(board, position, roots, bounds)
    # Fresh tokens reset engine state; legacy callers omit the argument.
    options = {"game": game} if game is not None else {}
    stream = await protocol.analysis(
        board,
        limit,
        multipv=len(roots) if reference else 2,
        root_moves=None if reference else roots,
        **options,
    )
    with stream:
        async for info in stream:
            state.add(info)
    return state


async def _timed(protocol, board, position, limit, roots, bounds, timeout, reference, game):
    return await asyncio.wait_for(
        _consume(protocol, board, position, limit, roots, bounds, reference, game), timeout
    )


def search(
    engine, board, position, limit, roots, deadline, *, bounds=None, reference=False, game=None
):
    remaining = deadline - time.monotonic() - CLEANUP_RESERVE
    if remaining <= 0:
        return None, "worker_deadline"
    timeout = min(remaining, engine.timeout + FINAL_SECONDS)
    coroutine = None
    try:
        protocol = engine.protocol
        coroutine = _timed(
            protocol, board, position, limit, roots, bounds, timeout, reference, game
        )
        future = asyncio.run_coroutine_threadsafe(coroutine, protocol.loop)
    except Exception:
        if coroutine is not None:
            coroutine.close()
        return None, "engine_failure"
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
