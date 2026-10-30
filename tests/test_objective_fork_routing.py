"""Fork jobs require the owned source, version and named objective together."""

from chess_coach.objective_fork_contract import GOAL, VERSION, is_source
from chess_coach.objective_promotion_routing import needs_verification


def test_colliding_public_or_unbound_sources_do_not_queue_owned_forks():
    row = {"source_type": "own-game", "source_version": VERSION, "objective": GOAL}
    assert is_source(row) and needs_verification(row)
    assert not is_source(row | {"source_type": "public"})
    assert not needs_verification(row | {"source_type": "public"})
    assert not is_source(row | {"source_version": "other"})
    assert not is_source(row | {"objective": "legal_line"})
