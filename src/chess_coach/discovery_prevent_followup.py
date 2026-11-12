"""Share remaining prevention time and count every attempted decision."""

from .discovery_mate_success_source import process_source as success_source
from .discovery_material_success_source import process_source as material_success_source


def remaining(db, source, started, mate, exclusions, successes):
    from .discovery_material_pipeline import process_source as material_source

    material = material_source(db, source, started)
    if _resolved(material):
        return {**material, "replayed": bool(mate["replayed"] and material["replayed"])}
    if material:
        exclusions[material["material_unresolved"]] += 1
    return _success(db, source, started, successes) or {**mate, "replayed": False}


def _success(db, source, started, successes):
    for source_fn, prefix in ((success_source, ""), (material_success_source, "material_")):
        result = source_fn(db, source, started)
        if result and "success_reason" not in result:
            # Both previous observations were examined under the same limit.
            return {**result, "replayed": False}
        if result and successes is not None:
            successes[prefix + result["success_reason"]] += 1
    return None


def _resolved(material):
    return bool(material) and "material_unresolved" not in material
