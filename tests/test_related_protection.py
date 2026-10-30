"""Operation-matched protection transfer from owned evidence to practice."""

import json

import pytest

from chess_coach.related_protection import preview
from chess_coach.related_protection_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import source_and_corpus
from tests.test_material_pipeline import LEARNER
from tests.test_objective_protection import oriented


@pytest.mark.parametrize("black", [False, True])
def test_owned_protection_transfer_is_concealed_playable_and_source_bound(
    tmp_path, monkeypatch, black
):
    db, evidence = source_and_corpus(tmp_path / "protection.sqlite", monkeypatch, black=black)
    result = preview(db, LEARNER, evidence, "test")
    assert result["status"] == "available" and len(result["items"]) == 1
    assert result["protection_scan"]["checked"] == 2
    item = result["items"][0]
    assert item["objective_target"] == ("d5" if black else "d4")
    assert oriented("d4d3", black) not in json.dumps(item)
    state = start_related(
        db,
        attempt_id="transfer",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    assert state["related_protection"] and state["protection_target"] == item["objective_target"]
    event = submit(db, "transfer", LEARNER, event_id="answer", move=oriented("d4d3", black))
    assert event["feedback"] == "line_match"
    assert show(db, "transfer", LEARNER)["status"] == "active"
    provenance = json.loads(
        db.connection.execute(
            "SELECT provenance_json FROM unified_sessions WHERE attempt_id='transfer'"
        ).fetchone()[0]
    )["related_protection"]
    assert provenance["operation"] == "prevent" and provenance["motif"] == "protection"
    assert provenance["evidence_id"] == evidence and provenance["pattern_cued"] is True
