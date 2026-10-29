"""Serialize native, root-relative engine results for one decision."""

import chess

from .analysis_score import native_score, native_wdl

SEMANTICS = "same-board-roots-v1"


def comparison_line(position, board, role, line):
    """Capture native score and a legal PV without inferring a skill outcome."""
    pv = _legal_pv(board, line.get("pv") or [])
    played = position["uci"]
    root_move = _root_move(role, played, pv)
    kind, value, bound = native_score(board, line)
    return {
        "position_id": position["id"],
        "role": role,
        "semantics": SEMANTICS,
        "decision_fen": board.fen(),
        "score_pov": "white" if board.turn else "black",
        "root_move": root_move,
        "score_kind": kind,
        "score_value": value,
        "score_bound": bound,
        "wdl_json": native_wdl(board, line),
        "pv": " ".join(pv) if pv else None,
        "nodes": line.get("nodes"),
        "depth": line.get("depth"),
        "seldepth": line.get("seldepth"),
        "time_seconds": line.get("time"),
    }


def _root_move(role, played, pv):
    if role == "played":
        if pv and pv[0] != played:
            raise ValueError("forced engine PV does not start with played move")
        return played
    return pv[0] if pv else None


def _legal_pv(board, moves):
    replay = board.copy()
    result = []
    for move in moves:
        if not isinstance(move, chess.Move) or move not in replay.legal_moves:
            raise ValueError("engine returned an illegal PV")
        result.append(move.uci())
        replay.push(move)
    return result


def save_comparison(connection, run_id, line):
    connection.execute(
        """INSERT INTO decision_analysis_lines
        (run_id,position_id,role,semantics,decision_fen,score_pov,root_move,score_kind,
        score_value,score_bound,wdl_json,pv,nodes,depth,seldepth,time_seconds)
        VALUES (:run_id,:position_id,:role,:semantics,:decision_fen,:score_pov,:root_move,
        :score_kind,:score_value,:score_bound,:wdl_json,:pv,:nodes,:depth,:seldepth,:time_seconds)""",
        {**line, "run_id": run_id},
    )
