"""Versioned identifiers for provisional pawn-endgame observations."""

PRODUCER = "pawn-endgame-observation"
MAPPER = "pawn-endgame-mapper"
VERSION = "1.0.0"
SKILL = "king_pawn_endgame"
FAMILY_SKILLS = frozenset({SKILL, "promotion"})
FACT_TYPE = "pawn_endgame_opportunity"
SCOPE = "pawn-endgame-choice"
