"""Version 1.1 closed-center pawn skeletons; not opening classifications."""

import chess

DEFINITIONS = {
    "french_advance": {
        "name": "French-like advance skeleton",
        "rule": "Advancing side d4/e5 against d5/e6, with the defending c-pawn on c5, c6 or c7. Exactly one pawn on each specified file; ranks reverse with colors.",
        "plans": "The advancing side may use kingside space; the defending side may challenge the chain with c5 or f6. Calculate before choosing a plan.",
        "source": "https://www.chess.com/article/view/pawn-structures-e5-d4-white-and-e6-d5-black",
    },
    "caro_advance": {
        "name": "Caro-Kann-like advance skeleton",
        "rule": "Advancing side d4/e5 against c6/d5, with the defending e-pawn on e6 or e7. Exactly one pawn on each specified file; ranks reverse with colors.",
        "plans": "The advancing side may use kingside space; the defending side may seek c5 to challenge d4. Calculate before choosing a plan.",
        "source": "https://www.chess.com/article/view/pawn-structures-e5-d4-white-and-e6-d5-black",
        "counterplan_source": "https://www.scacco.it/data/attachments/5593/or_caro-kann_extract.pdf",
    },
    "benoni": {
        "name": "Modern Benoni-like skeleton",
        "rule": "Advancing side d5/e4 against c5/d6; advancing c-file and defending e-file have no pawns, and each side has one a- and b-pawn. Exactly one pawn on each specified central file; ranks reverse with colors.",
        "plans": "The advancing side may prepare e5; the defending side may seek a b-pawn break for queenside counterplay. Calculate before choosing a plan.",
        "source": "https://www.chess.com/blog/Illingworth/mastering-pawn-structures-modern-benoni",
    },
}


def _on(pawns, file, ranks, flip):
    return len(pawns[file]) == 1 and chess.square_rank(pawns[file][0]) in {
        7 - rank if flip else rank for rank in ranks
    }


def _center(front, back, flip):
    return all(
        (
            _on(front, 3, (3,), flip),
            _on(front, 4, (4,), flip),
            _on(back, 3, (4,), flip),
        )
    )


def _french(front, back, flip):
    return _center(front, back, flip) and _on(back, 4, (5,), flip) and _on(back, 2, (4, 5, 6), flip)


def _caro(front, back, flip):
    return _center(front, back, flip) and _on(back, 2, (5,), flip) and _on(back, 4, (5, 6), flip)


def _benoni(front, back, flip):
    core = all((_on(front, 3, (4,), flip), _on(front, 4, (3,), flip), _on(back, 3, (5,), flip)))
    queenside = all(len(side[file]) == 1 for side in (front, back) for file in (0, 1))
    return core and _on(back, 2, (4,), flip) and not front[2] and not back[4] and queenside


def closed_center_matches(front, back, color, flip):
    """Label every matching skeleton from the advancing side's perspective."""
    return [
        {"family": family, "color": color, "square": None, "confidence": 1.0}
        for family, matched in (
            ("french_advance", _french(front, back, flip)),
            ("caro_advance", _caro(front, back, flip)),
            ("benoni", _benoni(front, back, flip)),
        )
        if matched
    ]
