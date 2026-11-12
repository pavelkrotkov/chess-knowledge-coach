"""Match only legal supplied defenses against the same material role."""

import chess

from .puzzle_session_validate import legal_move, solution_moves
from .related_capture_position import prompt_key
from .related_fork_lines import bind_lines
from .related_protection_proofs import matches


def scorer(budget):
    def candidate(item, source, seen, baseline):
        return _candidate(item, source, seen, baseline, budget)

    return candidate


def _candidate(item, source, seen, baseline, budget):
    try:
        prompt, lines = _prompt(item)
    except (ValueError, TypeError, KeyError):
        return None
    key = prompt_key(prompt)
    if key in seen:
        return None
    matched = matches(item, source, baseline, budget, prompt, key, lines)
    if not matched:
        return None
    best = min(matched, key=lambda entry: entry[0]["order"])[0]
    bind_lines(best, lines, [index for _, index in matched])
    return best


def _prompt(item):
    if item["type"] == "corpus":
        board = chess.Board(item["fen"])
        if not board.is_valid():
            raise ValueError("invalid setup")
        moves = solution_moves(item["solution"])
        board.push(legal_move(board, moves[0]))
        return board.fen(), [" ".join(moves[1:])]
    return item["fen"], item["lines"]
