"""Share remaining prevention time and count every attempted decision."""

from .discovery_mate_success_source import process_source as success_source


def remaining(db, source, started, mate, exclusions, successes):
    from .discovery_material_pipeline import process_source as material_source

    material = material_source(db, source, started)
    if _resolved(material):
        return {**material, "replayed": bool(mate["replayed"] and material["replayed"])}
    if material:
        exclusions[material["material_unresolved"]] += 1
    success = success_source(db, source, started)
    if success and "success_reason" not in success:
        # Material was examined even when both persisted outcomes replayed.
        return {**success, "replayed": False}
    if success and successes is not None:
        successes[success["success_reason"]] += 1
    return {**mate, "replayed": False}


def _resolved(material):
    return bool(material) and "material_unresolved" not in material
