"""Track the named pieces through a proposed defense."""

import chess


def matches(proof, defense, named):
    attacker = chess.Move.from_uci(proof["move"]).from_square
    return (
        chess.square_name(attacker) == named["attacker"]
        and proof["pinned"] == _after(defense, named["pinned"])
        and proof["rear"] == _after(defense, named["rear"])
        and proof["type"] == named["kind"]
    )


def _after(move, square):
    return (
        chess.square_name(move.to_square)
        if square == chess.square_name(move.from_square)
        else square
    )
