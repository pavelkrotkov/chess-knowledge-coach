"""Reject changed or incomplete promotion defense witnesses."""

import copy

import pytest

from chess_coach.objective_promotion_witness import choose
from tests.test_objective_promotion_proof_safety import proved_source


@pytest.mark.parametrize("change", ["status", "missing", "duplicate", "reply", "promotion"])
def test_promotion_proof_rejects_tampered_defenses(tmp_path, change):
    _, _, board, move, result = proved_source(tmp_path)
    board.push(move)
    proof = copy.deepcopy(result["proof"])
    assert choose(board, proof)["reply"] in {m.uci() for m in board.legal_moves}
    if change == "status":
        proof["status"] = "unknown"
    elif change == "missing":
        proof["witnesses"].pop()
    elif change == "duplicate":
        proof["witnesses"].append(proof["witnesses"][0])
    elif change == "reply":
        proof["witnesses"][0]["reply"] = "a1a2"
    else:
        proof["witnesses"][0]["promotion"] = "a7a8"
    with pytest.raises(ValueError):
        choose(board, proof)
