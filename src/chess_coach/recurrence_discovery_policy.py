"""Match discovery recurrence to the precise observed skill and operation."""

from .discovery_contract import FACT as DISCOVERY_FACT
from .discovery_contract import MAPPER as DISCOVERY_MAPPER
from .discovery_contract import PRODUCER as DISCOVERY_PRODUCER
from .discovery_contract import VERSION as DISCOVERY_VERSION
from .discovery_defense_contract import FACT as DISCOVERY_DEFENSE_FACT
from .discovery_defense_contract import MAPPER as DISCOVERY_DEFENSE_MAPPER
from .discovery_defense_contract import PRODUCER as DISCOVERY_DEFENSE_PRODUCER
from .discovery_defense_contract import VERSION as DISCOVERY_DEFENSE_VERSION
from .discovery_mate_success_contract import FACT as DISCOVERY_SUCCESS_FACT
from .discovery_mate_success_contract import MAPPER as DISCOVERY_SUCCESS_MAPPER
from .discovery_mate_success_contract import PRODUCER as DISCOVERY_SUCCESS_PRODUCER
from .discovery_mate_success_contract import VERSION as DISCOVERY_SUCCESS_VERSION
from .discovery_material_contract import FACT as DISCOVERY_MATERIAL_FACT
from .discovery_material_contract import MAPPER as DISCOVERY_MATERIAL_MAPPER
from .discovery_material_contract import PRODUCER as DISCOVERY_MATERIAL_PRODUCER
from .discovery_material_contract import VERSION as DISCOVERY_MATERIAL_VERSION


def discovery_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "execute",
        "discovered_attack",
    )


def discovery_defense_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "prevent",
        "discovery_mate_defense",
    )


def discovery_material_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "prevent",
        "discovery_material_defense",
    )


def discovery_success_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "prevent",
        "discovery_mate_success",
    )


FAMILIES = {
    DISCOVERY_MAPPER: (DISCOVERY_PRODUCER, DISCOVERY_VERSION, DISCOVERY_FACT),
    DISCOVERY_SUCCESS_MAPPER: (
        DISCOVERY_SUCCESS_PRODUCER,
        DISCOVERY_SUCCESS_VERSION,
        DISCOVERY_SUCCESS_FACT,
    ),
    DISCOVERY_MATERIAL_MAPPER: (
        DISCOVERY_MATERIAL_PRODUCER,
        DISCOVERY_MATERIAL_VERSION,
        DISCOVERY_MATERIAL_FACT,
    ),
    DISCOVERY_DEFENSE_MAPPER: (
        DISCOVERY_DEFENSE_PRODUCER,
        DISCOVERY_DEFENSE_VERSION,
        DISCOVERY_DEFENSE_FACT,
    ),
}

VALIDATORS = {
    DISCOVERY_MAPPER: discovery_ok,
    DISCOVERY_SUCCESS_MAPPER: discovery_success_ok,
    DISCOVERY_MATERIAL_MAPPER: discovery_material_ok,
    DISCOVERY_DEFENSE_MAPPER: discovery_defense_ok,
}
