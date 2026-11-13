"""Versioned identities and bounded supplied-line work for back-rank attack transfer."""

VERSION = "backrank-attack-transfer-v2"
FILTER_VERSION = "backrank-attack-lines-v2"
LINE_LIMIT = 128

DEFENSE_VERSION = "backrank-anchored-defense-transfer-v1"
DEFENSE_FILTER_VERSION = "backrank-anchored-defense-lines-v1"

CREATED_DEFENSE_VERSION = "backrank-created-defense-transfer-v1"
CREATED_DEFENSE_FILTER_VERSION = "backrank-created-defense-lines-v1"


def defense_version(source):
    return (
        CREATED_DEFENSE_VERSION
        if source.get("threat_origin") == "newly_allowed"
        else DEFENSE_VERSION
    )


def defense_filter(version):
    return (
        CREATED_DEFENSE_FILTER_VERSION
        if version == CREATED_DEFENSE_VERSION
        else DEFENSE_FILTER_VERSION
    )


def bound_defense_filter(key, provenance):
    if key != "related_backrank_defense":
        return DEFENSE_FILTER_VERSION
    if not isinstance(provenance, dict):
        raise ValueError("practice line selection unavailable")
    return defense_filter(provenance.get("rank_version"))
