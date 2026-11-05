"""Recheck one search batch against its owned source and novelty."""

from .fact_fingerprint import canonical, digest
from .related_capture_familiar import familiarity
from .related_capture_rank import rank
from .related_capture_source import baseline
from .related_mate_features import mate_features
from .related_mate_match import candidate
from .related_mate_search_corpus import corpus_info, root
from .related_mate_search_scan import scan
from .related_mate_search_token import fingerprint
from .related_mate_source import source_for_evidence


def select(db, subject, evidence, version, secret, state):
    source = source_for_evidence(db, subject, evidence)
    if source["objective"] != "mate_within_two":
        raise ValueError("short-mate search unavailable")
    rating = baseline(db, source)
    corpus = corpus_info(db, version, rating)
    if state["root"] != root(subject, version, source, rating, corpus):
        raise ValueError("search source changed; restart")
    familiar, games, probe = familiarity(db, subject)
    pool, next_keys, count = scan(db, version, corpus, state["keys"], games, secret)
    diagnostics = {}
    filtered = [
        item
        for item in pool
        if not item["game"] or fingerprint(secret, "game", item["game"]) not in state["games"]
    ]

    def known(key):
        return fingerprint(secret, "prompt", key) in state["prompts"] or probe(key)

    ordered = rank(
        source,
        filtered,
        familiar,
        rating,
        diagnostics,
        known,
        feature=mate_features,
        score=candidate,
    )
    diagnostics["duplicate"] += len(pool) - len(filtered)
    corpus["scanned"] = count
    scope = digest(
        canonical(
            [
                state["root"],
                state["keys"],
                state["prompts"],
                state["games"],
                pool,
                sorted(familiar),
                ordered,
            ]
        )
    )
    if state["scope"] is not None and state["scope"] != fingerprint(secret, "scope", scope):
        raise ValueError("search results changed; restart")
    return (source, rating, corpus, ordered, scope, diagnostics), next_keys
