"""Map each supported fork-prevention origin to its existing owned objective."""

from .fork_defense_contract import MAPPER
from .objective_fork_avoidance_contract import VERSION as AVOIDANCE
from .objective_fork_defense_contract import VERSION as DEFENSE


def identity(_db, _subject, evidence):
    if (evidence["mapping_producer"], evidence["skill"], evidence["operation"]) != (
        MAPPER,
        "fork",
        "prevent",
    ):
        raise ValueError("fork prevention unavailable")
    origin = evidence["facts"][0]["payload"].get("threat_origin")
    values = {
        "positional_before_played": (DEFENSE, "fork_defense"),
        "created_by_played_move": (AVOIDANCE, "fork_avoidance"),
    }
    version, kind = values.get(origin, (None, None))
    if version is None:
        raise ValueError("fork prevention unavailable")
    return version, str(evidence["id"]), kind
