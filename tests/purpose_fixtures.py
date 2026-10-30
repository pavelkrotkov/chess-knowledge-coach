"""Synthetic engine and private-view fixtures for purpose diagnostics."""

import sys

import chess
import chess.engine

from chess_coach.purpose_request import create
from tests.purpose_engine_fixture import CandidateEngine
from tests.test_deep_selection import LEARNER


def configure(monkeypatch, db, mode="normal", change=None):
    engine = CandidateEngine(db, mode, change)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _binary, timeout: engine)
    return engine


def request(db, position=1, learner=LEARNER):
    return create(db, position, learner, engine_path=sys.executable)["request_id"]
