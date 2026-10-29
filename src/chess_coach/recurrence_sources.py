"""Bounded, learner-owned source records for descriptive recurrence reports."""

from collections import Counter

from .evidence_review_facts import facts_for_evidence
from .learner_identity import learner_color, normalize_identity
from .mastery_game_lookup import decisions_for_game
from .repertoire_sources import games_for_learner

PAIRS = (
    ("hanging_piece", "execute"),
    ("hanging_piece", "prevent"),
    ("fork", "execute"),
    ("fork", "prevent"),
    ("mate_in_one", "execute"),
    ("calculation", "execute"),
    ("king_pawn_endgame", "execute"),
    ("king_pawn_endgame", "prevent"),
    ("king_pawn_endgame", "evaluate"),
    ("back_rank", "prevent"),
)
MAX_EVIDENCE = 300


def games(db, learner):
    rows, game_limit, scan_limit = games_for_learner(db, learner)
    states = Counter()
    for game, _ in rows:
        stage = db.connection.execute(
            "SELECT status FROM pipeline_stages WHERE game_id=? AND stage=?",
            (game["id"], "analysis"),
        ).fetchone()
        states[stage[0] if stage else "not analyzed"] += 1
    return {game["id"]: (game, color) for game, color in rows}, {
        "examined_games": len(rows),
        "analysis_stages": dict(states),
        "game_limit_reached": game_limit,
        "scan_limit_reached": scan_limit,
    }


def load_game(db, learner, game_id):
    game = db.connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if game is None:
        return None
    color = learner_color(game, learner)
    if color is None:
        return None
    if db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET 1000", (game_id,)
    ).fetchone():
        return None
    decisions = decisions_for_game(db, game_id, learner)
    if not decisions:
        return None
    identity = next(iter(decisions.values()))["game_key"]
    return {"row": game, "color": color, "decisions": decisions, "key": identity}


def evidence(db, learner, skill, operation):
    subject = normalize_identity(learner)
    rows = db.connection.execute(
        """SELECT e.*, p.game_id, p.ply, r.status AS mapping_status,
        r.producer AS mapping_producer, r.subject AS mapping_subject,
        r.position_id AS mapping_position, r.operation AS mapping_operation,
        r.mapper_version AS run_mapper_version,
        v.decision AS review_decision, v.actor AS review_actor
        FROM evidence_mappings e INDEXED BY idx_curriculum_evidence
        LEFT JOIN positions p ON p.id=e.position_id
        LEFT JOIN mapping_runs r ON r.id=e.mapping_run_id
        LEFT JOIN evidence_review_events v ON v.id=(SELECT id FROM evidence_review_events
            WHERE evidence_id=e.id ORDER BY id DESC LIMIT 1)
        WHERE e.subject=? AND e.skill=? AND e.operation=? ORDER BY e.id DESC LIMIT ?""",
        (subject, skill, operation, MAX_EVIDENCE + 1),
    ).fetchall()
    return rows[:MAX_EVIDENCE], len(rows) > MAX_EVIDENCE


def linked_fact(db, row):
    facts = facts_for_evidence(db, row["id"])
    if len(facts) != 1:
        return None
    valid = db.connection.execute(
        """SELECT 1 FROM evidence_fact_links WHERE evidence_id=? AND fact_id=? AND active=1
        AND subject=? AND skill=? AND operation=?""",
        (row["id"], facts[0]["id"], row["subject"], row["skill"], row["operation"]),
    ).fetchone()
    return facts[0] if valid else None
