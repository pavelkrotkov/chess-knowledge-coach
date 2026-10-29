"""Link competencies to existing capabilities and their verifiable behavior."""

from typing import Any

from .capabilities import capability_report
from .competency_graph import validate_graph
from .competency_seed import EDGES, GRAPH_VERSION, SKILLS

# Fixture references are test node names, not examples of inferred mastery.
COVERAGE: dict[str, dict[str, Any]] = {
    "mate_in_one": {
        "operation": "execute",
        "capabilities": ["mate_in_one_execute", "corpus_mate_practice"],
        "detector": "chess_coach.tactical_rules.mate_in_one_fact",
        "grading": "chess_coach.tactical_report.assess_fact; chess_coach.training_feedback_rules.assessment",
        "content": "Lichess corpus puzzles are candidates; the prompt and mating move must be verified, regardless of theme.",
        "fixtures": {
            "positive": "tests/test_tactical_opportunities.py::test_mate_candidates_are_legal_learner_decisions",
            "negative": "tests/test_training_feedback.py::test_declared_mate_task_nonmate_failure_is_unreviewed_evidence",
            "ambiguous": "tests/test_tactical_opportunities.py::test_engine_disagreement_is_ambiguous_without_changing_fact_identity",
        },
        "limits": "Game outcomes require review; hinted puzzle attempts add no skill evidence.",
    },
    "king_pawn_endgame": {
        "capabilities": ["manual_pawn_proof", "pawn_opportunities"],
        "detector": "chess_coach.pawn_coach_observation.observe",
        "limits": "Only proof-backed meaningful choices are mapped; family mastery remains closed pending independent validation. Practice completes supplied lines without general alternative grading.",
    },
    "fork": {
        "capabilities": ["tactical_geometry", "fork_opportunities", "fork_defense"],
        "detector": "chess_coach.fork_observation.observe",
        "limits": "Version 1.0.1 pawn and knight noncapturing execute observations may qualify for mastery after review and current source checks; version 1.0.0 knight-threat prevention may qualify after review and current source checks; broader fork mastery and fork practice remain unsupported.",
    },
    "hanging_piece": {
        "capabilities": ["tactical_geometry", "material_opportunities"],
        "detector": "chess_coach.material_observation.material_observation",
        "limits": "Provisional bounded material observations require review and independent validation before mastery eligibility.",
    },
    "absolute_pin": {
        "capabilities": ["tactical_geometry", "pin_opportunities"],
        "detector": "chess_coach.pin_observation.observe",
        "fixtures": {
            "positive": "tests/test_pin_observation.py::test_absolute_pin_requires_all_legal_replies",
            "negative": "tests/test_pin_observation.py::test_existing_pin_and_already_capturable_target_do_not_prove_creation",
            "ambiguous": "tests/test_pin_observation.py::test_defended_pinned_piece_does_not_become_a_material_claim",
        },
        "limits": "Bounded material or immediate mate proof; pin mastery remains closed pending qualification.",
    },
    "relative_pin": {
        "capabilities": ["pin_opportunities"],
        "detector": "chess_coach.pin_observation.observe",
        "fixtures": {
            "positive": "tests/test_pin_observation.py::test_relative_pin_execution_proves_each_reply_including_piece_moves",
            "negative": "tests/test_pin_observation.py::test_checking_counterplay_does_not_prove_exposure_loss",
            "ambiguous": "tests/test_pin_observation.py::test_relative_exposure_without_verified_defense_is_ambiguous",
        },
        "limits": "Bounded material or immediate mate proof; pin mastery remains closed pending qualification.",
    },
    "isolated_pawn": {
        "capabilities": ["structures"],
        "detector": "chess_coach.structure_features.extract_features",
    },
    "hanging_pawns": {
        "capabilities": ["structures"],
        "detector": "chess_coach.structure_features.extract_features",
    },
    "open_files": {
        "capabilities": ["structures"],
        "detector": "chess_coach.structure_features.extract_features",
    },
    "locked_center": {
        "capabilities": ["structures"],
        "detector": "chess_coach.structure_features.extract_features",
    },
    "space": {
        "capabilities": ["structures"],
        "detector": "chess_coach.structure_features.extract_features",
    },
    "opening_knowledge": {
        "capabilities": ["opening_classification"],
        "detector": "chess_coach.openings.classify_game",
    },
}


def competency_report() -> dict:
    """Return the same graph and registry-backed coverage to CLI and browser."""
    validate_graph(SKILLS, EDGES)
    registry = capability_report()
    capabilities = {entry["id"]: entry for entry in registry["capabilities"]}
    return {
        "version": GRAPH_VERSION,
        "capability_registry_version": registry["version"],
        "skills": [
            _entry(skill, description, capabilities) for skill, description in SKILLS.items()
        ],
        "edges": [{"from": a, "to": b, "type": kind} for a, b, kind in EDGES],
    }


def _entry(skill: str, description: str, capabilities: dict) -> dict:
    entry = COVERAGE.get(skill, {})
    linked = [capabilities[key] for key in entry.get("capabilities", [])]
    status = _status(linked)
    return {
        "skill": skill,
        "description": description,
        "operation": entry.get("operation"),
        "status": status,
        "detector": entry.get("detector"),
        "grading": entry.get("grading"),
        "content": entry.get("content"),
        "fixtures": dict(entry.get("fixtures", {})),
        "limits": entry.get(
            "limits", "No verified skill outcome or training grading is implemented."
        ),
        "capabilities": [{"id": item["id"], "status": item["status"]} for item in linked],
        "prerequisites": _relations(skill, "requires"),
        "supported_by": _relations(skill, "supports"),
    }


def _status(linked: list[dict]) -> str:
    if linked and all(item["status"] == "supported" for item in linked):
        return "supported"
    if any(item["status"] == "observation-only" for item in linked):
        return "observation-only"
    return "unsupported"


def _relations(skill: str, relation: str) -> list[str]:
    return [a for a, b, kind in EDGES if b == skill and kind == relation]
