"""Compose a source-linked lesson example."""

from .lesson_backrank import back_rank
from .lesson_lines import legal_san
from .lesson_material import _material as material
from .lesson_proofs import _mate as mate
from .lesson_proofs import _pawn as pawn
from .lesson_tactics import _defense as defense
from .lesson_tactics import _fork as fork

ADAPTERS = {
    "material-opportunity-mapper": material,
    "fork-opportunity-mapper": fork,
    "fork-defense-mapper": defense,
    "pawn-endgame-mapper": pawn,
    "bounded-mate-observation-mapper": mate,
    "back-rank-observation-mapper": back_rank,
}


def describe(source):
    evidence, decision = source["evidence"], source["decision"]
    fen = decision["decision_fen"]
    played = legal_san(fen, [decision["played_san"]])
    if not played:
        return None
    try:
        facts, lines = ADAPTERS[evidence["mapping_producer"]](evidence, fen)
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    if not facts:
        return None
    return {
        "evidence_id": evidence["id"],
        "fact_id": evidence["facts"][0]["id"],
        "detector_version": evidence["facts"][0]["detector_version"],
        "mapping_run_id": evidence["mapping_run_id"],
        "game_id": evidence["game_id"],
        "position_id": evidence["position_id"],
        "ply": evidence["ply"],
        "review": evidence["lesson_review"],
        "played": played[0],
        "facts": facts,
        "lines": [line for line in lines if line],
    }
