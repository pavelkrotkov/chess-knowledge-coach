"""Version 1.2 pawn skeletons; geometry does not establish opening history."""

from .closed_center_structures import _on

DEFINITIONS = {
    "maroczy": {
        "name": "Maróczy-like bind skeleton",
        "rule": "Bind side c4/e4 with no d-file pawn, opposing side no c-file pawn and exactly one d-pawn on d6 or d7; exactly one pawn on each specified occupied file. Ranks reverse with colors.",
        "plans": "Typical ideas, when the position and pieces allow: the bind side may restrict d5 and maneuver a remaining knight toward it; the opponent may seek a b-pawn or central break. These are not verified moves.",
        "source": "https://www.chess.com/article/view/the-maroczy-bind-by-gm-magesh-and-gm-arun",
    },
    "hedgehog": {
        "name": "Hedgehog-like compact skeleton",
        "rule": "Compact side has exactly one pawn on each of a6, b6, d6 and e6 and no c-file pawn; ranks reverse with colors. Opponent placement is unrestricted.",
        "plans": "Typical ideas, when the position and pieces allow: the compact side may develop a remaining bishop to b7 and prepare b5 or d5; the opponent may use space and seek a queenside advance. These are not verified moves.",
        "source": "https://en.chessbase.com/post/svitlana-s-smart-moves-learn-about-the-hedgehog-pawn-structure",
    },
    "sicilian_scheveningen": {
        "name": "Sicilian Scheveningen-like skeleton",
        "rule": "Space side e4 and c2, c3 or c4, no d-file pawn, against compact side d6/e6 with no c-file pawn; exactly one pawn on each specified occupied file. Ranks reverse with colors.",
        "plans": "Typical ideas, when the position and pieces allow: the space side may use the d-file or prepare f4-f5; the compact side may use the c-file and consider a d5 break. These are not verified moves.",
        "source": "https://simplifychess.com/pawn-structures/pawn-structure-101-sicilian-scheveningen/",
    },
    "sicilian_boleslavsky": {
        "name": "Sicilian Boleslavsky-like skeleton",
        "rule": "Space side e4 and c2, c3 or c4, no d-file pawn, against compact side d6/e5 with no c-file pawn; exactly one pawn on each specified occupied file. Ranks reverse with colors.",
        "plans": "Typical ideas, when the position and pieces allow: the space side may seek control of d5 with a remaining knight; the other side may seek queenside activity or a d5 break. These are not verified moves.",
        "source": "https://www.simplifychess.com/pawn-structures/pawn-structure-101-sicilian-boleslavsky-hole/index.html",
    },
}


def _maroczy(front, back, flip):
    return (
        _on(front, 2, (3,), flip)
        and _on(front, 4, (3,), flip)
        and not front[3]
        and not back[2]
        and _on(back, 3, (5, 6), flip)
    )


def _hedgehog(back, flip):
    return not back[2] and all(_on(back, file, (5,), flip) for file in (0, 1, 3, 4))


def _sicilian_center(front, back, flip, e_rank):
    return (
        _on(front, 4, (3,), flip)
        and _on(front, 2, (1, 2, 3), flip)
        and not front[3]
        and not back[2]
        and _on(back, 3, (5,), flip)
        and _on(back, 4, (e_rank,), flip)
    )


def sicilian_matches(front, back, front_color, back_color, flip):
    """Report all supported patterns, with the rule's identified side."""
    return [
        {"family": family, "color": color, "square": None, "confidence": 1.0}
        for family, color, matched in (
            ("maroczy", front_color, _maroczy(front, back, flip)),
            ("hedgehog", back_color, _hedgehog(back, flip)),
            ("sicilian_scheveningen", back_color, _sicilian_center(front, back, flip, 5)),
            ("sicilian_boleslavsky", back_color, _sicilian_center(front, back, flip, 4)),
        )
        if matched
    ]
