"""List eligible owned back-rank attack roots without inventing outcomes."""

from .back_rank_evidence import load

ROOT_LIMIT = 128


def roots(db, subject, evidence_id):
    evidence, fact, fingerprint = load(db, evidence_id, subject)
    if evidence["operation"] != "execute" or evidence["outcome"] not in {"success", "ambiguous"}:
        raise ValueError("back-rank attack source unavailable")
    if evidence["review_status"] not in {"accepted", "unreviewed"}:
        raise ValueError("back-rank attack source unavailable")
    alternatives = fact["payload"]["attack"].get("alternatives", [])
    if len(alternatives) > ROOT_LIMIT:
        raise ValueError("back-rank root limit exceeded")
    return (
        evidence,
        fact,
        fingerprint,
        [
            root
            for root in alternatives
            if root.get("status") == "proved" and root.get("distance_plies") in {1, 3}
        ],
    )
