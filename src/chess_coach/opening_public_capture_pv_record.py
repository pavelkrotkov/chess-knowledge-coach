"""Retain one source-attributed public capture observation."""

from .fact_fingerprint import canonical, digest
from .opening_public_proof_replay import _attribution


def record(connection, row, binding, rows, ply, board, move, measured, result):
    game_id, _, context = row
    value = {
        "ply": ply,
        "recorded_uci": move.uci(),
        "recorded_san": board.san(move),
        "history_sha256": digest(canonical(rows[: ply - 1])),
        **measured,
    }
    result["native_completed"] += 1
    result["native_qualified"] += int(measured["qualified"])
    _attribution(connection, game_id, context, binding, value)
    result["records"].append(value)
    observation = measured["observation"]
    if observation.get("outcome") in {"success", "failure"}:
        result["examples"].append(len(result["records"]) - 1)
    else:
        result["unsupported_positions"] += 1
        result["reasons"].append(observation.get("reason"))
