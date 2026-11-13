"""Build one source-bound unfamiliar worked example, when available."""

import chess

from .course_guidance import attribution
from .course_pgn import chapter
from .fact_fingerprint import canonical, digest
from .related_capture import VERSION as CAPTURE_VERSION
from .related_capture import _selection as capture_selection
from .related_fork import VERSION as FORK_VERSION
from .related_fork import selection as fork_selection
from .related_mate import VERSION as MATE_VERSION
from .related_mate import selection as mate_selection
from .related_protection import course_selection as protection_selection
from .related_transfer_admission import admit
from .tactical_course_protection import VERSION as PROTECTION_VERSION
from .unified_sources import resolve_source

FORK_CORPUS = "fork corpus unavailable"
FORK_EMPTY = "no compatible unfamiliar fork in the bounded scan"
HISTORY_LIMIT = "familiarity history exceeds the bounded scan"
GENERAL_EMPTY = "related corpus or compatible unfamiliar example unavailable"
PROTECTION_EMPTY = "no compatible unfamiliar protection in the bounded scan"
PROTECTION_CORPUS = "protection corpus unavailable"
PROTECTION_SOURCE = "protection teaching context unavailable"
PROTECTION_LIMIT = "protection proof limit reached"


def _selection(db, subject, corpus, choice, familiar_data, teaching_source):
    kind = choice["kind"]
    if kind == "protection":
        if teaching_source is None:
            raise ValueError("protection teaching source unavailable")
        selected = protection_selection(
            db, subject, teaching_source, corpus, familiar_data=familiar_data
        )
        return selected, PROTECTION_VERSION, "protection"
    if kind == "capture":
        selected = capture_selection(
            db, subject, choice["position_id"], corpus, familiar_data=familiar_data
        )
        return selected, CAPTURE_VERSION, "material_capture"
    if kind == "fork":
        selected = fork_selection(
            db, subject, choice["evidence_id"], corpus, familiar_data=familiar_data
        )
        return selected, FORK_VERSION, "fork"
    selected = mate_selection(
        db, subject, choice["evidence_id"], corpus, familiar_data=familiar_data
    )
    return selected, MATE_VERSION, "mate"


def with_reason(db, subject, corpus, choice, *, familiar_data=None, teaching_source=None):
    selected, version, motif = _selection(
        db, subject, corpus, choice, familiar_data, teaching_source
    )
    if selected is None:
        return None, {"fork": FORK_CORPUS, "protection": PROTECTION_CORPUS}.get(
            choice["kind"], GENERAL_EMPTY
        )
    if not selected[3]:
        return None, _empty(choice["kind"], selected)
    # Selection already excludes familiar prompts and binds the source.
    # Reuse its first bounded match without running an assessment verifier.
    if selected[0]["provenance"]["evidence_id"] != choice["evidence_id"]:
        raise ValueError("related source differs from selected lesson")
    item, scope = selected[3][0], selected[4]
    reference = digest(canonical([scope, item["type"], item["version"], item["key"]]))
    source_type, source_version, key, binding, matching = admit(selected, reference, version, motif)
    snapshot = resolve_source(db, source_type, source_version, key, subject=subject)
    if matching is not None:
        snapshot = {**snapshot, "lines": matching}
    provenance = {"type": source_type, "version": source_version, "key": key, "binding": binding}
    credit = attribution(db, source_type, source_version, snapshot)
    note = f"Pattern-cued unfamiliar worked example; other legal moves are ungraded. {credit}"
    if motif == "protection":
        board = chess.Board(snapshot["prompt_fen"])
        target = board.piece_type_at(chess.parse_square(item["objective_target"]))
        if target is None:
            raise ValueError("protected piece unavailable")
        action = {
            "move_threatened_piece": "moving the threatened piece",
            "capture_attacker": "capturing the attacker",
            "interpose": "interposing a piece",
            "guard": "adding a defender",
            "indirect_defense": "an indirect defense",
        }[item["protection_mechanism"]]
        note = (
            f"Protect the {chess.piece_name(target)} by {action}. "
            "The bounded check found no profitable immediate capture of the named piece. "
            "Your recorded source action remains provisional. "
            f"Other moves and later risks remain ungraded. {credit}"
        )
    return chapter("Related unfamiliar example", note, snapshot, provenance), None


def unfamiliar(db, subject, corpus, choice, *, familiar_data=None, teaching_source=None):
    return with_reason(
        db, subject, corpus, choice, familiar_data=familiar_data, teaching_source=teaching_source
    )[0]


def _empty(kind, selected):
    if kind == "protection":
        return PROTECTION_LIMIT if selected[2]["protection_scan"]["truncated"] else PROTECTION_EMPTY
    return FORK_EMPTY if kind == "fork" else GENERAL_EMPTY
