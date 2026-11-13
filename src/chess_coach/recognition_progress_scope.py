"""Match current uncued prompts on their recorded, comparable context."""


def scope(db, row, proof):
    rating, deviation = row["content_rating"], row["content_deviation"]
    if type(rating) is not int or type(deviation) is not int or min(rating, deviation) < 0:
        return None
    corpus = db.connection.execute(
        "SELECT checksum FROM puzzle_corpora WHERE version=? AND state='ready'",
        (row["source_version"],),
    ).fetchone()
    if corpus is None or not isinstance(corpus["checksum"], str) or not corpus["checksum"]:
        return None
    kind = proof["kind"]
    policy = _policy(proof)
    start, spread = rating // 200 * 200, deviation // 100 * 100
    key = (
        row["source_version"],
        corpus["checksum"],
        kind,
        policy,
        row["learner_color"],
        start,
        spread,
    )
    return {
        "key": key,
        "kind": kind,
        "color": row["learner_color"],
        "rating": start,
        "deviation": spread,
    }


def _policy(proof):
    if proof["kind"] == "mate":
        return (
            proof["version"],
            proof["history_mode"],
            proof["mate_verifier"],
            proof["capture_verifier"],
        )
    saved = proof["proof"]
    return (
        proof["version"],
        saved["history_mode"],
        saved["version"],
        saved["proof_version"],
        saved["gain_threshold"],
    )
