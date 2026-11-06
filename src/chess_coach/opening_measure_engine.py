"""Compare two selected roots in one bounded native engine search."""

from .deep_execution_engine import start_engine, stop_engine
from .opening_measure_search import search
from .purpose_deadline import cleanup_timeout, startup_timeout


def measure(binary, config, board, position, alternative, deadline):
    timeout = startup_timeout(deadline)
    if timeout is None:
        return {"status": "insufficient", "reason": "deadline"}
    runtime = dict(config)
    try:
        engine, metadata = start_engine(binary, runtime, timeout=timeout)
    except RuntimeError:
        return {"status": "insufficient", "reason": "engine_start_failed"}
    try:
        result = search(engine, board, position, alternative, deadline)
        result["engine"] = dict(metadata.id)
        result["runtime_engine"] = {
            key: runtime.get(key) for key in ("engine_id", "nnue_options", "native_wdl_requested")
        }
    finally:
        engine.timeout = cleanup_timeout(deadline)
        stopped = stop_engine(engine)
    if not stopped:
        return {"status": "insufficient", "reason": "engine_shutdown_failed"}
    return result
