"""Replay complete owned games and count legal immediate-mate opportunities."""

from .learner_context import decision_context_boards
from .mastery_game_identity import game_identity
from .mastery_position import position_key
from .mate_game_eligibility import require_consistent_result, require_game
from .mate_proof import immediate_mates


def prepared_game(db, game, learner):
    require_game(db, game)
    pairs = list(decision_context_boards(db, game["id"], learner=learner))
    if not pairs:
        raise ValueError("game has no decisions")
    for context, board in pairs:
        if board.outcome(claim_draw=False):
            raise ValueError("moves continue after game termination")
        context["prompt_fen"] = position_key(board)
    require_consistent_result(game, pairs)
    key = game_identity(db, game["id"], [context for context, _ in pairs])
    return key, pairs


def game_outcomes(pairs):
    opportunities, misses, examples = 0, 0, []
    for context, board in pairs:
        if not context["subject"]:
            continue
        mates = immediate_mates(board)
        if not mates:
            continue
        opportunities += 1
        missed = not any(move["uci"] == context["played_move"] for move in mates)
        misses += missed
        examples.append({"position_id": context["position_id"], "missed": missed})
    return opportunities, misses, examples
