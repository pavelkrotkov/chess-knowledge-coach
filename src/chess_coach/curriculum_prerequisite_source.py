"""Bind the existing back-rank topic to its witnessed, current owned source."""

from .back_rank_evidence import load
from .competency_seed import EDGES, GRAPH_VERSION, SKILLS
from .competency_validation import validate_graph
from .curriculum_prerequisite_witness import select_witness
from .decision_history import decision_board
from .fact_fingerprint import canonical, digest
from .mate_inspection_source import position_row
from .objective_defense_freshness import review_id
from .objective_defense_policy import eligible
from .objective_source_budget import within_budget
from .pawn_scope import history_known

POLICY = "back-rank-m1-prerequisite-v1"
LIMIT = 20


def graph():
    validate_graph(SKILLS, EDGES)
    if ("mate_in_one", "back_rank_mate", "requires") not in EDGES:
        raise ValueError("prerequisite relation unavailable")
    return digest(canonical([GRAPH_VERSION, SKILLS, EDGES, POLICY]))


def context(db, subject, limit, check):
    check()
    # Check the indexed source cardinality before any full witness inspection.
    rows = db.connection.execute(
        """SELECT id FROM evidence_mappings INDEXED BY idx_curriculum_evidence
        WHERE subject=? AND skill='back_rank' AND operation='prevent'
        ORDER BY id DESC LIMIT ?""",
        (subject, min(limit, LIMIT) + 1),
    ).fetchall()
    if len(rows) > min(limit, LIMIT):
        return {"state": "incomplete", "scope": digest(canonical([POLICY, "incomplete"]))}
    for row in rows:
        check()
        try:
            result = _current(db, subject, row["id"], check)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
        if result:
            return result
    return {"state": "unavailable", "scope": digest(canonical([POLICY, "unavailable"]))}


def _current(db, subject, evidence_id, check):
    if not within_budget(db, evidence_id, subject):
        return None
    check()
    evidence, fact, fingerprint = load(db, evidence_id, subject)
    if not eligible(db, evidence, fact):
        return None
    board = _board(db, evidence, fact)
    if board is None:
        return None
    defense = fact["payload"]["defense"]
    witness = select_witness(board, defense, evidence["outcome"], check)
    if witness is None:
        return None
    check()
    review = review_id(db, evidence_id)
    # The cursor carries only this digest, never the private source identifier.
    scope = digest(canonical([POLICY, graph(), subject, evidence_id, fingerprint, review, witness]))
    return {"state": "available", "scope": scope, "review": evidence["review_status"]}


def _board(db, evidence, fact):
    position = position_row(db, evidence["position_id"])
    board = decision_board(db, position)
    played = position["uci"]
    if fact["payload"]["played"] != played or fact["payload"]["defense"]["played"] != played:
        return None
    if board.fen() != evidence["decision_fen"] or not board.is_valid() or not history_known(board):
        return None
    if board.is_game_over(claim_draw=True):
        return None
    board.parse_uci(played)
    return board
