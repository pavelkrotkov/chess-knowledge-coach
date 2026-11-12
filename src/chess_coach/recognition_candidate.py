"""Prove one unfamiliar bounded corpus candidate."""

from .recognition_exposures import sessions
from .recognition_proof import prove
from .related_capture_assessment import setup
from .related_capture_candidates import _game_id
from .related_capture_position import prompt_key


def candidate(db, subject, version, row, kind, familiar, games, seen, check):
    try:
        source_game = _game_id(row["source"])
        if source_game in games:
            return None
        prepared = setup(db, version, row["puzzle_id"])
        board, _, fingerprint = prepared
        key = prompt_key(board.fen())
        if not _unfamiliar(db, subject, key, familiar, seen, check):
            return None
        proof = prove(db, version, row["puzzle_id"], kind, prepared)
        if not proof or proof["source_fingerprint"] != fingerprint:
            return None
        return {
            "source_version": version,
            "source_key": row["puzzle_id"],
            "prompt_fen": board.fen(),
            "prompt_key": key,
            "learner_color": "white" if board.turn else "black",
            "source_fingerprint": fingerprint,
            "proof": proof,
            "rating": row["rating"],
            "source_url": row["source"],
            "source_game": source_game,
            "deviation": row["rating_deviation"],
            "opening": row["opening"],
        }
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def _unfamiliar(db, subject, key, familiar, seen, check):
    return not (key in familiar or seen(key) or sessions(db, subject, key, check))
