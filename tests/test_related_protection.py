"""Operation-matched protection transfer from owned evidence to practice."""

import json

import pytest

from chess_coach.related_protection import preview
from chess_coach.related_protection_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import learning_counts, source_and_corpus
from tests.test_material_pipeline import LEARNER
from tests.test_objective_protection import oriented


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize(("played", "outcome"), [("a2a3", "failure"), ("d4d5", "success")])
def test_owned_protection_transfer_is_concealed_playable_and_source_bound(
    tmp_path, monkeypatch, black, played, outcome
):
    db, evidence = source_and_corpus(
        tmp_path / "protection.sqlite", monkeypatch, black=black, played=played
    )
    result = preview(db, LEARNER, evidence, "test")
    assert (
        result["status"],
        len(result["items"]),
        result["protection_scan"]["checked"],
        result["source_outcome"],
    ) == ("available", 1, 2, outcome)
    item = result["items"][0]
    assert item["objective_target"] == ("d5" if black else "d4")
    assert oriented("d4d3", black) not in json.dumps(item)
    before = learning_counts(db)
    state = start_related(
        db,
        attempt_id="transfer",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    assert (state["related_protection"], state["protection_target"]) == (
        True,
        item["objective_target"],
    )
    event = submit(db, "transfer", LEARNER, event_id="answer", move=oriented("d4d3", black))
    assert (event["feedback"], show(db, "transfer", LEARNER)["status"]) == ("line_match", "active")
    assert learning_counts(db) == before
    provenance = json.loads(
        db.connection.execute(
            "SELECT provenance_json FROM unified_sessions WHERE attempt_id='transfer'"
        ).fetchone()[0]
    )["related_protection"]
    assert (
        provenance["operation"],
        provenance["motif"],
        provenance["evidence_id"],
        provenance["pattern_cued"],
    ) == ("prevent", "protection", evidence, True)
