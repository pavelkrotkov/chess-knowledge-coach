"""Bind a queued request to the exact current source and engine settings."""

from .fact_fingerprint import canonical, digest
from .opening_measure_prepare import _config
from .opening_measure_source import selection
from .opening_queue_budget import BrowserBudget

ENGINE = "/usr/games/stockfish"
VERSION = "opening-queue-v1"


def identity(database, source, config):
    return digest(canonical([VERSION, database, source, config]))


def snapshot(db, database, learner, game, position, alternative):
    budget = BrowserBudget(db)
    with budget.scope(snapshot=False):
        source, owned = selection(db, game, position, learner, alternative)
    with budget.scope(snapshot=False):
        _, config = _config(db, game, ENGINE)
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
