"""Current analyzed-game eligibility for independent board proofs."""

from .deep_selection_checkpoint import validate_checkpoint
from .deep_selection_source_rows import current_analysis
from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .mate_game_sample import prepared_game
from .short_mate_game_source import _signature
from .style_time_candidates import verified
from .style_time_query import load_game


def binding(db, game_id):
    stage, run, config = current_analysis(db, game_id)
    validate_checkpoint(db, game_id, stage, config)
    return digest(canonical([dict(stage), dict(run)]))


def prepare(db, learner, game_id):
    subject = normalize_identity(learner)
    game = load_game(db.connection, game_id)
    if not subject or game is None or verified(game, subject) is None:
        raise ValueError("game unavailable")
    before = _signature(db, game)
    identity, pairs = prepared_game(db, game, subject)
    current = load_game(db.connection, game_id)
    if current is None or verified(current, subject) is None or _signature(db, current) != before:
        raise ValueError("game changed during replay")
    return {
        "game_id": game_id,
        "started_at": game["projected_start"],
        "identity": identity,
        "signature": before,
        "pairs": pairs,
    }
