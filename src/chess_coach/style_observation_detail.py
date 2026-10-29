"""Build one source-linked comparable choice observation."""

import chess

from .deep_execution_views import deep_for_position
from .style_compare import candidates
from .style_context import describe_context
from .style_dimensions import dimensions


def observation(db, learner, context, item, selected, opening):
    board = chess.Board(context["pre_move_fen"])
    deep = deep_for_position(db, context["position_id"], learner, board, context["played_move"])
    compared = candidates(board, context["played_move"], deep)
    status = compared["status"] if deep else item["status"]
    covered = bool(
        deep
        and deep.get("result")
        and any(
            line["line"]["root_move"] == context["played_move"]
            for line in deep["result"]["alternatives"]
        )
    )
    completed = bool(deep and deep["status"] == "complete")
    if status != "comparable":
        return status, None, covered, completed
    result = compared["run"]
    return (
        status,
        {
            "game_id": context["game_id"],
            "position_id": context["position_id"],
            "ply": context["ply"],
            "played_move": context["played_move"],
            "context": describe_context(db, context, opening),
            "game_outcome": context["game_outcome"],
            "allocation": item["allocation"],
            "selection_reasons": item["reasons"],
            "selection_id": selected["selection_id"],
            "selector_version": selected["selector_version"],
            "cheap_run_id": selected["cheap_run_id"],
            "deep_job_id": deep["job_id"],
            "attempt_number": deep["attempt_number"],
            "analysis_run_id": result["run_id"],
            "engine": result["engine"],
            "engine_version": result["engine_version"],
            "limits": result["limits"],
            "legal_roots": board.legal_moves.count(),
            "ranked_roots": len(result["alternatives"]),
            "played_line": compared["played"],
            "same_search_gap_cp": _score_gap(result, compared["played"]),
            "pairs": compared["pairs"],
            "choices": dimensions(compared["pairs"]),
        },
        covered,
        completed,
    )


def _score_gap(result, played):
    best = result["alternatives"][0]["line"]
    if best["score_kind"] != "cp" or best["score_bound"] != "exact":
        return None
    return played["score_value"] - best["score_value"]
