"""Bounded attributable games and reviewed source evidence for repertoire views."""

from collections import Counter

from .learner_identity import learner_color, normalize_identity
from .named_structure_intervals import game_history
from .named_structures import VERSION
from .repertoire_limit import MAX_GAMES, validate_limit

MAX_SCAN = 1000


def games_for_learner(db, learner, *, limit=MAX_GAMES):
    limit = validate_limit(limit)
    if normalize_identity(learner) is None:
        raise ValueError("learner identity is unavailable")
    rows = db.connection.execute("SELECT * FROM games ORDER BY id DESC LIMIT ?", (MAX_SCAN + 1,))
    games = []
    scanned = 0
    for row in rows:
        scanned += 1
        if scanned > MAX_SCAN:
            break
        color = learner_color(row, learner)
        if color:
            games.append((row, color))
            if len(games) > limit:
                break
    return games[:limit], len(games) > limit, scanned > MAX_SCAN


def reviewed_failures(db, game_id, learner, color):
    return [
        dict(row)
        for row in db.connection.execute(
            """SELECT e.id,e.skill,e.operation,p.ply FROM evidence_mappings e
        JOIN positions p ON p.id=e.position_id JOIN mapping_runs r ON r.id=e.mapping_run_id
        JOIN evidence_review_events v ON v.id=(SELECT id FROM evidence_review_events
            WHERE evidence_id=e.id ORDER BY id DESC LIMIT 1)
        WHERE p.game_id=? AND e.subject=? AND e.outcome='failure'
        AND r.status='active' AND r.subject=e.subject AND r.position_id=e.position_id
        AND instr(p.fen, ?) > 0 AND v.decision='accept' ORDER BY p.ply,e.id""",
            (game_id, normalize_identity(learner), " b " if color == "white" else " w "),
        )
    ]


def structures(db, game_id, color):
    if not db.connection.execute(
        "SELECT 1 FROM structure_runs WHERE game_id=? AND status='active'", (game_id,)
    ).fetchone():
        return {"status": "not extracted", "families": [], "truncated": False}
    items, unmatched, truncated = game_history(db, game_id, color, VERSION)
    counts = Counter(item["family"] for item in items)
    return {
        "status": "extracted",
        "families": sorted(counts),
        "unmatched_positions": unmatched,
        "truncated": bool(truncated),
    }
