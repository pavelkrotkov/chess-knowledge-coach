"""Map lesson sources to their family-specific currentness fields."""

STATES = {
    "discovery-material-success-mapper": "discovery_material_success_currentness",
    "discovery-opportunity-mapper": "discovery_currentness",
    "discovery-mate-defense-mapper": "discovery_defense_currentness",
    "discovery-mate-success-mapper": "discovery_success_currentness",
    "discovery-material-defense-mapper": "discovery_material_currentness",
    "pin-execute-mapper": "pin_source_currentness",
    "pin-prevent-mapper": "pin_source_currentness",
    "material-opportunity-mapper": "material_source_currentness",
    "fork-opportunity-mapper": "fork_source_currentness",
    "fork-defense-mapper": "fork_defense_currentness",
    "bounded-mate-observation-mapper": "mate_source_currentness",
    "pawn-endgame-mapper": "pawn_source_currentness",
    "back-rank-observation-mapper": "back_rank_source_currentness",
    "king-safety-lesson-mapper": "king_safety_currentness",
    "pawn-structure-lesson-mapper": "pawn_structure_currentness",
    "rook-plan-lesson-mapper": "rook_plan_currentness",
}
