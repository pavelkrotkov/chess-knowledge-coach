"""Show an owned slide only after the stronger source is available."""

from .objective_pin_slide_contract import VERSION
from .objective_pin_slide_source import resolve


def available(db, evidence, subject):
    try:
        if (
            evidence.get("pin_source_currentness") != "current"
            or evidence.get("operation") != "prevent"
            or evidence["facts"][0]["payload"]["proof"]["type"] != "relative_pin"
            or evidence["facts"][0]["payload"]["proof"]["mode"] != "exposure"
        ):
            return False
        resolve(db, VERSION, str(evidence["id"]), subject)
        return True
    except (ValueError, KeyError, TypeError, IndexError):
        return False
