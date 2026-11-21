"""Extract normalized positions from every legal PGN variation."""

import io

import chess.pgn

from .ingest_reader import SilentGameBuilder
from .tactical_exposure_positions import MAX_POSITIONS, position_key


def _game(pgn):
    if not isinstance(pgn, str) or len(pgn.encode("utf-8")) > 4 * 1024 * 1024:
        raise ValueError("tactical chapter unavailable")
    stream = io.StringIO(pgn)
    game = chess.pgn.read_game(stream, Visitor=SilentGameBuilder)
    if game is None or game.errors or chess.pgn.read_game(stream, Visitor=SilentGameBuilder):
        raise ValueError("tactical chapter unavailable")
    return game


def positions(pgn):
    game = _game(pgn)
    board = game.board()
    result, count = {position_key(board)}, 0
    stack = [(node, board.copy()) for node in game.variations]
    while stack:
        node, position = stack.pop()
        if node.move not in position.legal_moves:
            raise ValueError("tactical continuation is illegal")
        position.push(node.move)
        result.add(position_key(position))
        count += 1
        if count > MAX_POSITIONS:
            raise ValueError("tactical chapter exceeds exposure limit")
        stack.extend((child, position.copy()) for child in node.variations)
    return result
