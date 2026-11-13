"""Screen and prove one reset-history unfamiliar defense."""

import chess

from .back_rank_candidate import candidate as eligible
from .puzzle_session_validate import CORPUS_PLIES_LIMIT, legal_move, solution_moves, validate_line
from .related_backrank_defense_proof import proof
from .related_capture_match import _scored
from .related_capture_position import _features, prompt_key
from .related_capture_rank import _excluded
from .related_fork_lines import bind_lines

PROOF_LIMIT = 4


def _prompt(item, source):
    if item["type"] != "corpus":
        return None
    board = chess.Board(item["fen"])
    moves = solution_moves(item["solution"])
    if not board.is_valid() or len(moves) > CORPUS_PLIES_LIMIT:
        return None
    setup = legal_move(board, moves[0])
    if not board.is_zeroing(setup):
        return None
    board.push(setup)
    king = board.king(board.turn)
    if king is None or not eligible(board, board.turn):
        return None
    if chess.square_file(king) != source["threat_shape"][0]:
        return None
    return board, moves


def scorer(source, budget, familiar_data):
    familiar, _, is_familiar = familiar_data
    source_key = prompt_key(source["prompt_fen"])

    def score(item, source_features, seen, baseline):
        try:
            candidate = _prompt(item, source)
            if candidate is None:
                return None
            board, moves = candidate
            key = prompt_key(board.fen())
            if key in seen:
                return None
            exclusion = _excluded(key, source_key, familiar, is_familiar)
            if exclusion:
                budget[exclusion] += 1
                return None
            # Charge full replay and legal proof only after the cheap geometry screen.
            if budget["proofs"] >= PROOF_LIMIT:
                budget["truncated"] = True
                return None
            budget["proofs"] += 1
            if validate_line(item["fen"], item["solution"]) != board.fen():
                return None
            move = legal_move(board, moves[1])
            witness = proof(board, move, source)
            if witness is None:
                return None
            features = _features(
                board,
                move,
                board.piece_at(move.from_square),
                board.piece_at(board.king(board.turn)),
            )
            result = _scored(item, source_features, features, board.fen(), key, baseline)
            bind_lines(result, [" ".join(moves[1:])], [0])
            result["defense_witness"] = witness
            return result
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            return None

    return score
