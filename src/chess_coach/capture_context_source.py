"""Bind one admitted capture witness to its exact retained game root."""

import chess

from .capture_context_presence import pattern
from .curriculum_capture_practice import evidence
from .fact_fingerprint import canonical
from .objective_capture_source import resolve
from .related_capture_position import _features, _supported_move


def _match(snapshot, position, observation, turns):
    board = chess.Board(snapshot["prompt_fen"])
    move = board.parse_uci(snapshot["lines"][0])
    mover, target = board.piece_at(move.from_square), board.piece_at(move.to_square)
    if not _supported_move(board, move, mover, target):
        return None
    features = _features(board, move, mover, target)
    shape = {key: features[key] for key in ("mover", "target", "geometry")}
    if canonical(shape) != canonical(observation["pattern"]):
        return None
    matches = [
        (turn, root)
        for turn in turns
        if turn["position_id"] == position and turn["side"] == observation["side"]
        for root in turn["roots"]
        if root["move"] == move.uci()
        and root["target_square"] == snapshot["provenance"]["objective_target"]
        and root["state"] == "proved"
        and root["mechanism"] == "direct"
        and canonical(root["features"]) == canonical(features)
    ]
    if len(matches) != 1:
        return None
    turn, root = matches[0]
    context = canonical([turn["side"], turn["time_control"], turn["phase"], turn["material"]])
    return context, pattern(turn, root), turn["time_control"]


def bind(db, subject, corpus, as_of, option, turns, check):
    candidate, report = option
    position = report["source"]["position_id"]
    if report["limited"]:
        return None
    observed = evidence(
        db, subject, corpus, position, report["history"], as_of, check, project=True
    )
    if observed is None:
        return None
    snapshot = resolve(
        db, candidate["source_version"], candidate["source_key"], subject, check=check
    )
    provenance = snapshot["provenance"]
    if (provenance["position_id"], snapshot["learner_color"]) != (position, observed["side"]):
        return None
    if observed["source"] != tuple(
        provenance[key] for key in ("evidence_id", "source_fingerprint", "review_event_id")
    ):
        return None
    matched = _match(snapshot, position, observed, turns)
    if matched is None:
        return None
    context, key, control = matched
    return {
        "position": position,
        "controls": observed["controls"],
        "side": observed["side"],
        "tier": observed["result"],
        "time_control": control,
        "wanted": (context, key),
    }
