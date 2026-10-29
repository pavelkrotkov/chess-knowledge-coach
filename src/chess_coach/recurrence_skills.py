"""Skill and operation pairs with supported candidate producers."""

PAIRS = (
    ("discovered_attack", "execute"),
    ("hanging_piece", "execute"),
    ("hanging_piece", "prevent"),
    ("fork", "execute"),
    ("fork", "prevent"),
    ("mate_in_one", "execute"),
    ("calculation", "execute"),
    ("king_pawn_endgame", "execute"),
    ("king_pawn_endgame", "prevent"),
    ("king_pawn_endgame", "evaluate"),
    ("back_rank", "prevent"),
    ("back_rank", "execute"),
    ("pawn_structure", "evaluate"),
    ("absolute_pin", "execute"),
    ("absolute_pin", "prevent"),
    ("relative_pin", "execute"),
    ("relative_pin", "prevent"),
    ("open_files", "evaluate"),
    ("king_safety", "evaluate"),
)
