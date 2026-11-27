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
        result = measured(engine, metadata, runtime, config, board, position, alternative, deadline)
    finally:
        engine.timeout = cleanup_timeout(deadline)
        stopped = stop_engine(engine)
    if not stopped:
        return {"status": "insufficient", "reason": "engine_shutdown_failed"}
    return result


def measured(
    engine, metadata, runtime, config, board, position, alternative, deadline, *, game=None
):
    if config.get("purpose_policy") == "opening-catalog-reference-v2":
        options = {"game": game} if game is not None else {}
        result = _reference(
            engine, metadata, config, board, position, alternative, deadline, **options
        )
    else:
        result = search(engine, board, position, alternative, deadline)
    result["engine"] = dict(metadata.id)
    result["runtime_engine"] = {
        key: runtime.get(key) for key in ("engine_id", "nnue_options", "native_wdl_requested")
    }
    return result


def _reference(engine, metadata, config, board, position, alternative, deadline, *, game=None):
    # The native option must support the exact number of legal roots requested.
    count = board.legal_moves.count()
    option = metadata.options.get("MultiPV")
    if (
        option is None
        or option.type != "spin"
        or option.min is None
        or option.max is None
        or not option.min <= count <= option.max
        or count != config["multipv"]
    ):
        return {"status": "insufficient", "reason": "multipv_unavailable"}
    options = {"game": game} if game is not None else {}
    result = search(engine, board, position, alternative, deadline, reference=True, **options)
    result["effective_multipv"] = count
    result["multipv_max"] = option.max
    return result
