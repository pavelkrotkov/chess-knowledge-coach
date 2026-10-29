"""Versioned, deliberately scoped product capability report.

Update this registry alongside the feature and its behavioral tests.
"""

REGISTRY_VERSION = "1.9.0"

CAPABILITIES = (
    {
        "id": "staged_puzzle_corpus",
        "area": "Training",
        "name": "Staged local puzzle corpus",
        "status": "supported",
        "details": "Official snapshots can be acquired and staged in bounded batches with optional declared subset provenance; only legally validated, completed versions become available. Live broad activation remains planned.",
    },
    {
        "id": "competency_graph",
        "area": "Skill coverage",
        "name": "Competency graph and coverage",
        "status": "supported",
        "details": "A versioned taxonomy displays prerequisites and implementation coverage; it does not add detectors or establish mastery.",
    },
    {
        "id": "mate_in_one_execute",
        "area": "Skill coverage",
        "name": "Mate in one",
        "status": "supported",
        "details": "Automatic legal mate-in-one opportunities; nonterminal missed mates remain ambiguous and evidence requires review.",
    },
    {
        "id": "tactical_geometry",
        "area": "Skill coverage",
        "name": "Forks, hanging pieces and absolute pins",
        "status": "observation-only",
        "details": "Manual static motif detection describes board geometry; it does not establish a reliable decision opportunity or outcome.",
    },
    {
        "id": "structures",
        "area": "Skill coverage",
        "name": "Pawn structures and board features",
        "status": "observation-only",
        "details": "Atomic episodes and conservative IQP, Carlsbad, French-like, Caro-Kann-like, Benoni-like, Maróczy-like, Hedgehog-like, Scheveningen-like and Boleslavsky-like history describe positions; they do not establish positional skill failures. Other named families remain planned.",
    },
    {
        "id": "tactical_decisions",
        "area": "Skill coverage",
        "name": "Tactical opportunities and defense",
        "status": "planned",
        "details": "Verified loose-material, fork, pin, skewer, discovered-attack, back-rank and defensive opportunities and outcomes are not yet automatic.",
    },
    {
        "id": "positional_endgame",
        "area": "Skill coverage",
        "name": "Positional and endgame decisions",
        "status": "planned",
        "details": "Grounded positional lessons and verified elementary endgame decisions are not yet available.",
    },
    {
        "id": "manual_deep_selection",
        "area": "Analysis",
        "name": "Manual selection for deep analysis",
        "status": "supported",
        "details": "A bounded manual selector records possible opportunities and control samples; automatic scheduling remains planned.",
    },
    {
        "id": "manual_deep_execution",
        "area": "Analysis",
        "name": "Manual bounded deep analysis",
        "status": "supported",
        "details": "Selected positions can be analyzed with bounded best, played and MultiPV searches; automatic scheduling remains planned.",
    },
    {
        "id": "decision_comparison",
        "area": "Analysis",
        "name": "Best versus played decision analysis",
        "status": "supported",
        "details": "Two bounded searches compare the best and forced played move on the same decision board; manual selective deep searches are available; automatic scheduling remains planned.",
    },
    {
        "id": "corpus_mate_practice",
        "area": "Training",
        "name": "Verified public-corpus mate practice",
        "status": "supported",
        "details": "The daily plan selects legally verified mate-in-one corpus tasks and schedules individual items with FSRS.",
    },
    {
        "id": "own_game_practice",
        "area": "Training",
        "name": "Own-game exercises",
        "status": "planned",
        "details": "Game positions are not yet generated as playable, verified training exercises.",
    },
    {
        "id": "broader_practice",
        "area": "Training",
        "name": "Related public and canonical exercises",
        "status": "planned",
        "details": "Multi-skill related retrieval, canonical lessons and alternative-aware grading are not yet supported.",
    },
    {
        "id": "adaptive_curriculum",
        "area": "Training",
        "name": "Multi-skill adaptive curriculum",
        "status": "planned",
        "details": "The current plan is restricted to mate-in-one; broader skills, prerequisites and difficulty adaptation remain planned.",
    },
    {
        "id": "mastery_v2",
        "area": "Progress",
        "name": "Reviewed evidence and mastery heuristic",
        "status": "supported",
        "details": "An uncalibrated, recency-weighted outcome heuristic requires three independent, current, reviewed contexts; engine loss is not mastery.",
    },
    {
        "id": "recurring_report",
        "area": "Progress",
        "name": "Recurring patterns and improvement",
        "status": "planned",
        "details": "Cross-skill recurring patterns with contextual opportunity counts and separate practice/game progress are not yet provided.",
    },
    {
        "id": "explanation_adapter",
        "area": "Explanation",
        "name": "Optional explanation adapter",
        "status": "supported",
        "details": "A trusted injectable callable can store text from supplied facts; it is not wired into automatic coaching and is not a security sandbox.",
    },
    {
        "id": "grounded_coaching",
        "area": "Explanation",
        "name": "Grounded coaching explanations",
        "status": "planned",
        "details": "Automatic coach-like explanations, source-linked reasoning and practical advice are not yet available.",
    },
    {
        "id": "opening_classification",
        "area": "Repertoire",
        "name": "Opening classification",
        "status": "observation-only",
        "details": "Imported opening data supports classification and history; it does not yet recommend repertoire changes or new openings.",
    },
    {
        "id": "repertoire_recommendations",
        "area": "Repertoire",
        "name": "Repertoire and new-opening recommendations",
        "status": "planned",
        "details": "Context-aware current-line improvements and new-opening recommendations remain planned.",
    },
    {
        "id": "private_course_publication",
        "area": "Publication",
        "name": "Personalized private Lichess courses",
        "status": "planned",
        "details": "Course generation and verified private Study upload are not yet implemented.",
    },
)


def capability_report() -> dict:
    """Return a JSON-compatible snapshot without exposing mutable registry entries."""
    return {"version": REGISTRY_VERSION, "capabilities": [dict(item) for item in CAPABILITIES]}
