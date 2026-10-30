"""Construct legal synthetic engine lines."""

import io

import chess
import chess.engine
import chess.pgn

from tests.test_deep_selection import PGN


def played_move(board):
    game = chess.pgn.read_game(io.StringIO(PGN))
    assert game is not None
    return list(game.mainline_moves())[len(board.move_stack)]


def candidate_roots(board, root_moves, mode):
    if root_moves is not None:
        return root_moves
    played = played_move(board)
    alternatives = [move for move in board.legal_moves if move != played]
    return alternatives[:2] if mode == "scout_without_played" else [played, alternatives[0]]


def principal_variation(board, move, short):
    replay = board.copy()
    replay.push(move)
    pv = [move]
    for _ in range(3):
        follow = next(iter(replay.legal_moves))
        pv.append(follow)
        replay.push(follow)
    return pv[:1] if short else pv


def assert_outside_transaction(db):
    if db is not None:
        assert not db.connection.in_transaction
