"""Show a verified created pin and one of its legal proof branches."""

from .lesson_adapter_common import line, valid_square


def created(evidence, note, fen):
    proof = note["proof"]
    if not valid_square(proof.get("pinned")) or not valid_square(proof.get("rear")):
        return [], []
    sample = note.get("sample") or {}
    moves = [
        *_prefix(evidence, note),
        proof["san"],
        sample.get("reply_san"),
        sample.get("capture_san"),
    ]
    tested = line(fen, "One tested pin defense and capture", moves)
    replies = proof.get("legal_replies")
    if not tested or type(replies) is not int or replies < 1:
        return [], []
    san, pinned, rear = proof["san"], proof["pinned"], proof["rear"]
    facts = [
        f"The tested move {san} pins the piece on {pinned} against {rear}.",
        f"Each of {replies} legal immediate replies has a tested capture with a bounded material gain or immediate checkmate.",
    ]
    return facts, [tested]


def _prefix(evidence, note):
    if evidence["operation"] == "execute":
        return []
    alternative = note.get("alternative") or {}
    reasons = {"other_immediate_threat_unresolved", "compensation_unresolved"}
    if alternative and (note.get("outcome") == "success" or note.get("reason") in reasons):
        return [alternative.get("san")]
    return [evidence["lesson_played_san"]]
