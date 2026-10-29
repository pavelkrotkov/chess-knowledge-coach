"""A game imported through two real routes contributes only once for a generic skill."""

from datetime import UTC, datetime

import httpx
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.ingest import ingest_pgn
from chess_coach.lichess import LichessClient
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.mastery import update_mastery

NOW = 1_800_000_000


def pgn(game_id, timestamp):
    when = datetime.fromtimestamp(timestamp, UTC)
    return f"""[Event "Synthetic"]
[Site "https://lichess.org/{game_id}"]
[GameId "{game_id}"]
[White "Learner"]
[Black "Opponent"]
[UTCDate "{when:%Y.%m.%d}"]
[UTCTime "{when:%H:%M:%S}"]
[Variant "Standard"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


class Export:
    def __init__(self, raw):
        self.raw = raw

    def get(self, url, **kwargs):
        params = kwargs["params"]
        inside = params.get("since", 0) <= (NOW - 60) * 1000 < params.get("until", NOW * 1000 + 1)
        return httpx.Response(
            200, text=self.raw if inside else "", request=httpx.Request("GET", url)
        )


def map_game(db, game_id):
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? AND ply=1", (game_id,)
    ).fetchone()[0]
    when = db.connection.execute("SELECT pgn FROM games WHERE id=?", (game_id,)).fetchone()[0]
    from chess_coach.learner_time import observation_time

    observed = observation_time(when)
    fact = record_fact_run(
        db,
        position_id=position,
        producer="fixture",
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "fixture_skill", "payload": {}}],
    )
    with mapping_transaction(db):
        result = record_mapping_run_in_transaction(
            db,
            position_id=position,
            producer="fixture",
            mapper_version="v1",
            subject="learner",
            operation="execute",
            scope_key="fixture",
            input_data={},
            mappings=[
                {
                    "skill": "fixture_skill",
                    "outcome": "success",
                    "confidence": 1,
                    "fact_ids": fact["fact_ids"],
                    "context": {},
                    "observation_at": observed,
                }
            ],
        )
    review_evidence(db, result["evidence_ids"][0], decision="accept", actor="fixture-reviewer")


def test_cross_source_game_identity_ignores_pgn_formatting(monkeypatch):
    monkeypatch.setattr("chess_coach.lichess.time.time", lambda: NOW)
    db = Database(":memory:")
    db.initialize()
    raw = pgn("synthetic1", NOW - 60)
    client = LichessClient(client=Export(raw), retries=0)
    assert client.sync_user(db, "learner", max_games=100, page_size=2)["games"] == 1
    local = raw.replace("1. e4 e5", "1. e4 {annotation and clock} e5")
    ingest_pgn(db, local, source="local")
    ingest_pgn(db, pgn("synthetic2", NOW - 120), source="local")
    for game_id in range(1, 4):
        map_game(db, game_id)
    now = datetime.fromtimestamp(NOW, UTC)
    partial = update_mastery(
        db, subject="learner", skill="fixture_skill", operation="execute", as_of=now
    )
    assert partial["context_count"] == 2 and partial["status"] == "insufficient"
    assert partial["exclusions"] == {"duplicate_context": 1}
    ingest_pgn(db, pgn("synthetic3", NOW - 180), source="local")
    map_game(db, 4)
    result = update_mastery(
        db, subject="learner", skill="fixture_skill", operation="execute", as_of=now
    )
    assert result["context_count"] == 3 and result["status"] == "sufficient"
    assert result["effective_weight"] == pytest.approx(3)
    assert result["mastery"] == 1 and result["uncertainty"] == pytest.approx(0.25)
    assert result["exclusions"] == {"duplicate_context": 1}
