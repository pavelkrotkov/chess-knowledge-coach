"""Retain optional exact roots from the existing fork classifier pass."""

from .capture_game_root_detail import inspect as inspect_roots

POLICY = "knight-fork-game-roots-v1"
REFRESH_VERSION = f"{POLICY}:refresh-v1"


def start_details(details, board, played):
    if details is not None:
        details.update(
            side="white" if board.turn else "black",
            played=played,
            total=None,
            attempted=0,
            roots=[],
        )


def observe(observations, move, proof, state):
    if observations is not None:
        observations.append((move, proof, state))


def append_root(details, move, proof, state):
    if details is not None:
        details["attempted"] += 1
        if len(details["roots"]) < 32:
            details["roots"].append([move.uci(), proof["targets"] if proof else [], state])


def finish_details(details):
    if details is not None:
        total = details["total"]
        details["unsearched"] = None if total is None else total - details["attempted"]


def inspect(db, learner, item, deadline, quota, *, state, classifier, seconds):
    from .fork_game_proof import VERSION

    return inspect_roots(
        db,
        learner,
        item,
        deadline,
        quota,
        state=state,
        classifier=classifier,
        seconds=seconds,
        version=POLICY,
        proof=VERSION,
        refresh_version=REFRESH_VERSION,
    )
