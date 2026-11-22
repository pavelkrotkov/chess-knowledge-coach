"""Bind a queued request to the exact current source and engine settings."""

from .fact_fingerprint import canonical, digest
from .opening_measure_source import selection
from .opening_queue_budget import BrowserBudget
from .purpose_config import configuration

V1 = "opening-catalog-comparison-v1"
V2 = "opening-catalog-reference-v2"


def _config(db, game_id, engine, board=None, policy=V1):
    binary, config = configuration(db, game_id, engine)
    config = dict(config)
    config.pop("scout_nodes")
    config.pop("scout_seconds")
    config.update(
        {
            "purpose": "opening-catalog-comparison",
            "purpose_policy": policy,
            "candidate_set": "played-and-selected-catalog",
        }
    )
    if policy == V2:
        if board is None:
            raise ValueError("opening board unavailable")
        config.update(
            {
                "candidate_set": "all-legal-roots",
                "multipv": board.legal_moves.count(),
                "requested_nodes": 180000,
                "requested_seconds": 1.35,
            }
        )
    elif policy != V1:
        raise ValueError("opening comparison policy unavailable")
    return binary, config


ENGINE = "/usr/games/stockfish"
VERSION = "opening-queue-v1"


def identity(database, source, config):
    return digest(canonical([VERSION, database, source, config]))


def snapshot(db, database, learner, game, position, alternative, *, deadline=None, budget=None):
    # A caller with a pinned snapshot supplies its existing non-nested budget.
    if budget is None:
        budget = BrowserBudget(db)
    if deadline is not None:
        budget.expires = min(budget.expires, deadline)
    with budget.scope(snapshot=False):
        source, owned = selection(db, game, position, learner, alternative)
    with budget.scope(snapshot=False):
        _, config = _config(db, game, ENGINE, owned["board"], V2)
    return budget, source, config, owned


def request(database, source, config, attempt=0):
    return {
        "version": VERSION,
        "id": identity(database, source, config),
        "database": database,
        "source": source,
        "configuration": config,
        "attempt": attempt,
        "state": "queued",
    }


def legacy_config(config):
    if config.get("purpose_policy") != V2:
        return None
    result = dict(config)
    result.pop("requested_nodes")
    result.pop("requested_seconds")
    result.update(
        {"purpose_policy": V1, "candidate_set": "played-and-selected-catalog", "multipv": 2}
    )
    return result
