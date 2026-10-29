"""Assemble an attributable game and its current opening provenance."""

from .classification_inputs import opening_input
from .fact_fingerprint import canonical, digest
from .learner_identity import learner_color
from .repertoire_positions import position_data
from .repertoire_sources import reviewed_failures, structures


def _opening(db, game_id):
    return db.connection.execute(
        """SELECT d.version,d.source_url,d.content_revision,n.name,n.eco,n.position_key,
        r.classifier_version,r.id run_id,r.input_hash,r.pipeline_generation,d.id dataset_id FROM current_game_openings o
        JOIN opening_datasets d ON d.id=o.dataset_id JOIN opening_runs r ON r.id=o.run_id
        LEFT JOIN opening_nodes n ON n.id=o.opening_node_id WHERE o.game_id=?""",
        (game_id,),
    ).fetchone()


def _outcome(result, color):
    if result == "1/2-1/2":
        return "draw"
    if result not in ("1-0", "0-1"):
        return "unknown"
    return "win" if (result == "1-0") == (color == "white") else "loss"


def _stale(db, game_id, opening):
    value = opening_input(db, game_id, opening["dataset_id"])
    if opening["pipeline_generation"] is not None:
        value = digest(
            canonical({"base": value, "pipeline_generation": opening["pipeline_generation"]})
        )
    return value != opening["input_hash"]


def game_report(db, game, color, learner):
    opening = _opening(db, game["id"])
    other = "black" if color == "white" else "white"
    return {
        "id": game["id"],
        "color": color,
        "result": game["result"],
        "outcome": _outcome(game["result"], color),
        "date": game["date"],
        "time_control": game["time_control"],
        "learner_rating": game[f"{color}_elo"],
        "opponent_rating": game[f"{other}_elo"],
        "opening": dict(opening) if opening else None,
        "classification_stale": _stale(db, game["id"], opening) if opening else False,
        **position_data(db, game["id"], opening),
        "structures": structures(db, game["id"], color),
        "evidence": reviewed_failures(db, game["id"], learner, color),
    }


def game_detail(db, learner, game_id):
    game = db.connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    color = learner_color(game, learner) if game else None
    if not color:
        raise ValueError("game is unavailable")
    return game_report(db, game, color, learner)
