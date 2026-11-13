"""Select unfamiliar supplied lines after bounded created-exposure proof."""

import time

from .pawn_scope import history_known
from .related_capture_match import _scored
from .related_capture_position import _features, prompt_key
from .related_capture_rank import _excluded
from .related_created_line import line as prove_line
from .related_created_proof import nominations
from .related_fork_lines import bind_lines
from .related_pin_candidates import prompt

SECONDS = 8


def scorer(source, familiar_data, budget):
    familiar, _, indexed = familiar_data
    source_key = prompt_key(source["prompt_fen"])

    def score(item, features, seen, baseline):
        try:
            return _score(item, features, baseline, budget, familiar, indexed, source_key)
        except (ValueError, TypeError, KeyError, IndexError):
            return None

    return score


def _score(item, source, baseline, budget, familiar, indexed, source_key):
    if budget["truncated"] or time.monotonic() >= budget["deadline"]:
        budget["truncated"] = True
        return None
    board, lines = prompt(item)
    if not history_known(board) or len(list(board.legal_moves)) > 64:
        return None
    for index, text in enumerate(lines):
        result = _item(
            item, source, baseline, budget, familiar, indexed, source_key, board, lines, index, text
        )
        if result is not None:
            return result
    return None


def _item(item, source, baseline, budget, familiar, indexed, source_key, board, lines, index, text):
    line = text.split()
    if not line:
        return None
    good = board.parse_uci(line[0])
    # Discard unrelated geometry and familiar positions before reserving proof work.
    moves = nominations(board, good, source)
    if not moves or _excluded(prompt_key(board.fen()), source_key, familiar, indexed):
        return None
    witness = prove_line(board, line, good, moves, budget)
    if witness:
        return _result(
            item, source, baseline, board, prompt_key(board.fen()), lines, index, witness
        )
    return None


def _result(item, source, baseline, board, key, lines, index, witness):
    bad = board.parse_uci(witness["bad"])
    after = board.copy()
    after.push(bad)
    capture = after.parse_uci(witness["capture"])
    shape = _features(
        board, bad, board.piece_at(bad.from_square), after.piece_at(capture.from_square)
    )
    result = _scored(item, source, shape, board.fen(), key, baseline)
    bind_lines(result, lines, [index])
    result["created_witness"] = witness
    return result
