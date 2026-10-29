"""Family gates retain their order when several exclusions apply."""

import pytest

from chess_coach import mastery_content


@pytest.mark.parametrize(
    "back_rank,mate,pawn,fork,material,expected",
    [
        (True, False, False, "fork", False, "back_rank_family_unvalidated"),
        (False, False, False, "fork", False, "mate_family_unvalidated"),
        (False, True, False, "fork", False, "pawn_family_unvalidated"),
        (False, True, True, "fork", False, "fork"),
        (False, True, True, None, False, "material_family_unvalidated"),
        (False, True, True, None, True, None),
    ],
)
def test_family_gate_priority(monkeypatch, back_rank, mate, pawn, fork, material, expected):
    monkeypatch.setattr(mastery_content, "back_rank_closed", lambda _row: back_rank)
    monkeypatch.setattr(mastery_content, "mate_mastery_allowed", lambda *_: mate)
    monkeypatch.setattr(mastery_content, "pawn_mastery_allowed", lambda *_: pawn)
    monkeypatch.setattr(mastery_content, "family_reason", lambda *_: fork)
    monkeypatch.setattr(mastery_content, "mastery_allowed", lambda *_: material)
    monkeypatch.setattr(mastery_content, "valid_confidence", lambda *_: True)
    monkeypatch.setattr(mastery_content, "valid_links", lambda *_: True)
    assert mastery_content.content_reason(None, {"outcome": "success", "confidence": 1}) == expected
