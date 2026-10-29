"""Build an explicit owned one-move immediate-mate defense objective."""

from .back_rank_evidence import load
from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_defense_exemplar import choose
from .objective_defense_freshness import require_unchanged, review_id
from .objective_defense_policy import eligible
from .objective_defense_snapshot import OBJECTIVE as OBJECTIVE
from .objective_defense_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known

VERSION = "avoid-immediate-mate-own-v1"


def resolve(db, version, key, subject):
    if not _valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("defense objective unavailable")
    evidence, fact, fingerprint = load(db, int(key), subject)
    if not eligible(db, evidence, fact):
        raise ValueError("defense objective unavailable")
    board = decision_board(db, position_row(db, evidence["position_id"]))
    if not history_known(board) or board.is_game_over(claim_draw=True):
        raise ValueError("defense history unavailable")
    review = review_id(db, evidence["id"])
    text = choose(board, fact["payload"])
    require_unchanged(db, subject, evidence, fact, fingerprint, review)
    return snapshot(db, board, evidence, fact, fingerprint, text)


def _valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
