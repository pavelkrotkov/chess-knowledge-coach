"""Identify the exact verified pin mechanism and source policy."""

import chess


def pattern(snapshot, item):
    provenance = snapshot["provenance"]
    named, proof = provenance["pin_prevention"], provenance["pin_witness"]
    board = chess.Board(snapshot["prompt_fen"])
    # Classify the witnessed geometry after the bad move, including source policy.
    if named["origin"] == "created":
        board.push_uci(named["bad"])
        board.push_uci(proof["move"])
    squares = [chess.parse_square(proof[key]) for key in ("pinner", "pinned", "rear")]
    pieces = tuple(board.piece_type_at(square) for square in squares)
    if None in pieces:
        raise ValueError("pin geometry unavailable")
    anchor = squares[1]
    geometry = tuple(
        (
            chess.square_file(s) - chess.square_file(anchor),
            chess.square_rank(s) - chess.square_rank(anchor),
        )
        for s in squares
    )
    return (
        item["version"],
        provenance["mapper_version"],
        named["kind"],
        named["origin"],
        proof.get("mode"),
        pieces,
        geometry,
    )
