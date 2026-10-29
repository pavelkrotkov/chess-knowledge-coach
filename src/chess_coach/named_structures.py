"""Conservative named pawn geometries, independent of opening labels."""

import chess

VERSION = "1.0.0"

# Descriptions are educational patterns, not verified moves in the current position.
DEFINITIONS = {
    "iqp": {
        "name": "Isolated queen pawn",
        "rule": "A d-file pawn with no friendly pawns on either adjacent file.",
        "plans": "The pawn side may seek activity and a pawn advance; the opponent may blockade and pressure the pawn. Calculate before choosing a plan.",
        "source": "https://www.chess.com/article/view/attack-and-defense-in-the-iqp",
    },
    "carlsbad": {
        "name": "Carlsbad skeleton",
        "rule": "Minority side d4/e3 versus c6/d5, with a- and b-pawns on both sides, no minority c-pawn or majority e-pawn, and no additional central pawns; ranks reverse with colors.",
        "plans": "The minority side may advance the b-pawn to challenge the c-pawn or prepare a central break. The majority side may use its a-pawn to resist the minority advance. These are typical ideas, not verified advice for this position.",
        "source": "https://www.chess.com/terms/carlsbad-pawn-structure-chess",
        "counterplan_source": "https://nscfchess.org/plans-for-both-sides-in-the-carlsbad-structure/",
    },
}


def _files(board, color):
    return {file: list(board.pieces(chess.PAWN, color) & chess.BB_FILES[file]) for file in range(8)}


def _iqps(pawns, color):
    if pawns[2] or pawns[4]:
        return []
    return [
        {"family": "iqp", "color": color, "square": chess.square_name(sq), "confidence": 1.0}
        for sq in pawns[3]
    ]


def _squares_match(pawns, expected, flip):
    return all(
        pawns[file] == [chess.square(file, 7 - rank if flip else rank)]
        for file, rank in expected.items()
    )


def _carlsbad(minority, majority, color, flip):
    central = _squares_match(minority, {3: 3, 4: 2}, flip) and _squares_match(
        majority, {2: 5, 3: 4}, flip
    )
    queenside = all(len(side[file]) == 1 for side in (minority, majority) for file in (0, 1))
    if not central or minority[2] or majority[4] or not queenside:
        return []
    return [{"family": "carlsbad", "color": color, "square": None, "confidence": 1.0}]


def match_structures(board):
    """Return every exact supported match; color is IQP owner or Carlsbad minority."""
    white, black = _files(board, chess.WHITE), _files(board, chess.BLACK)
    return (
        _iqps(white, "white")
        + _iqps(black, "black")
        + _carlsbad(white, black, "white", False)
        + _carlsbad(black, white, "black", True)
    )
