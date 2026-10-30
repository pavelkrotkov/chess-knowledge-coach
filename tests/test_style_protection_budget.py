"""Work limits keep unexamined protection choices unknown."""

import pytest

from chess_coach.style_protection_budget import create, take


def test_work_budget_is_shared_by_resolutions_and_proofs():
    budget = create(limit=2)
    assert take(budget, "resolutions")
    assert take(budget, "proofs")
    assert not take(budget, "proofs")
    assert budget["used"] == budget["limit"] == 2
    assert budget["resolutions"] == budget["proofs"] == 1
    assert budget["skipped"] == 1


def test_zero_budget_never_starts_expensive_work():
    budget = create(limit=0)
    assert not take(budget, "resolutions")
    assert budget["used"] == 0 and budget["skipped"] == 1


def test_exemplar_reservation_is_required_before_resolver(monkeypatch):
    import chess_coach.style_protection_source as source

    monkeypatch.setattr(source, "resolve", lambda *args: pytest.fail("unreserved proof"))
    budget = create(limit=1)
    assert source.load(None, "fixture", 1, budget) is None
    assert budget["resolutions"] == 1 and budget["proofs"] == 0
    assert budget["skipped"] == 1


def test_exhausted_root_reservation_never_invokes_verifier(monkeypatch):
    import chess_coach.style_protection_proof as module

    monkeypatch.setattr(module, "judge", lambda *args: pytest.fail("unreserved verifier"))
    result = module.proof(None, "a1a2", 0, {}, 1, create(limit=0))
    assert result == {"status": "unknown", "reason": "report_budget_exhausted"}
