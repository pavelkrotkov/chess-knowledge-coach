"""Bind a prepared public proof to current owned selection and source bytes."""

from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES
from .objective_capture_judge import VERSION as VERIFIER
from .opening_fit_later_index import locate
from .opening_measure_source import selection
from .opening_profile_owned_control import control
from .opening_profile_play import STORED_PLIES
from .opening_public_proof_index import check, index_hash
from .opening_queue_location import location
from .style_time_candidates import verified
from .style_time_query import load_game

VERSION = "public-opening-capture-preparation-v1"
MAX_GAMES = 10
MAX_POSITIONS = 36
SECONDS = 30
PROOF_SECONDS = 20


def binding(db, root, subject, game_id, position_id, alternative, deadline):
    check(deadline)
    _, database = location(db, root, subject)
    source, owned = selection(db, game_id, position_id, subject, alternative)
    game = load_game(db.connection, game_id)
    color = "white" if owned["board"].turn else "black"
    ply = owned["position"]["ply"]
    if (
        verified(game, subject) != color
        or not 1 <= ply <= 20
        or (ply % 2 == 1) != (color == "white")
    ):
        raise ValueError("owned decision unavailable")
    index = locate(root, subject, "recent")
    checksum = index_hash(index[0], deadline)
    if locate(root, subject, "recent") != index:
        raise ValueError("public reference changed")
    check(deadline)
    return {
        "version": VERSION,
        "database": database,
        "source": source,
        "color": color,
        "ply": ply,
        "control": control(game),
        "reference": index[3],
        "index_sha256": checksum,
        "transform": index[2],
        "policy": {
            "objective": "capture_named_target",
            "verifier": VERIFIER,
            "minimum_gain": 3,
            "reply_limit": MAX_REPLIES,
            "exchange_nodes": MAX_EXCHANGE_NODES,
            "exchange_plies": MAX_EXCHANGE_PLIES,
            "games_per_branch": MAX_GAMES,
            "positions": MAX_POSITIONS,
            "stored_plies": STORED_PLIES,
            "shared_seconds": SECONDS,
            "proof_seconds": PROOF_SECONDS,
        },
    }, index
