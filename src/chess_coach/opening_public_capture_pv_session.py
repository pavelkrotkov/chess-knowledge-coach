"""Run one bounded public capture preparation with one native engine."""

from .deep_execution_engine import start_engine, stop_engine
from .deep_execution_lock import deep_lock
from .engine_report_cache import report_digests
from .opening_measure_engine import measured
from .opening_public_comparison_engine import configuration
from .opening_public_proof_prepare import branches
from .opening_public_proof_source import PROOF_SECONDS, check
from .purpose_deadline import cleanup_timeout, startup_timeout


def prepare_selected(
    database,
    binary,
    index,
    base,
    start,
    deadline,
    *,
    forks,
    prevent,
    protection,
    capture_pv,
    defense_pv,
    window,
):
    if defense_pv:
        from .opening_public_defense_pv_policy import policy as defense_policy

        identity = defense_policy(
            base,
            forks=forks,
            prevent=prevent,
            protection=protection,
            capture_pv=capture_pv,
            window=window,
        )
    else:
        from .opening_public_capture_pv_policy import policy as capture_policy

        identity = capture_policy(
            base,
            forks=forks,
            prevent=prevent,
            protection=protection,
            window=window,
        )
    result, sample = prepare(database, binary, index, identity, start, deadline)
    return identity, result, sample


def prepare(database, binary, index, identity, start, deadline):
    state = {"binary": binary, "engine": None, "failed": False}
    with report_digests(), deep_lock(database):
        try:
            return branches(
                index, identity, start, start + PROOF_SECONDS, capture_pv=True, engine=state
            )
        finally:
            engine = state["engine"]
            if engine is not None:
                engine.timeout = cleanup_timeout(deadline)
                if not stop_engine(engine):
                    raise ValueError("public capture engine shutdown failed")


def _start(state, binary, config, deadline):
    timeout = startup_timeout(deadline)
    if timeout is None:
        return "deadline"
    runtime = dict(config)
    try:
        engine, metadata = start_engine(binary, runtime, timeout=timeout)
    except RuntimeError:
        state["failed"] = True
        return "engine_start_failed"
    state.update(engine=engine, metadata=metadata, runtime=runtime, configuration=config)
    return None


def analyze(board, move, state, deadline):
    check(deadline)
    if state["failed"]:
        raise ValueError("public capture engine unavailable")
    # The public history replay already checks this pre-move board and its legal move.
    binary, config = configuration(state["binary"], board)
    if state["engine"] is None:
        reason = _start(state, binary, config, deadline)
        if reason:
            return config, {"status": "insufficient", "reason": reason}
    try:
        original = state["configuration"]
        if {**config, "multipv": original["multipv"]} != original:
            raise ValueError("public capture engine configuration changed")
        result = measured(
            state["engine"],
            state["metadata"],
            state["runtime"],
            config,
            board,
            {"id": None, "uci": move},
            move,
            deadline,
            game=object(),
        )
        _, current = configuration(state["binary"], board)
        if current != config:
            raise ValueError("public capture engine configuration changed")
    except BaseException:
        state["failed"] = True
        raise
    if result.get("reason") in {"worker_deadline", "engine_timeout", "engine_failure"}:
        state["failed"] = True
    check(deadline)
    return config, result
