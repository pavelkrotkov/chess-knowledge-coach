"""Choose one optional canonical promotion practice without writing progress."""

from .objective_promotion_contract import FORCE, NOW
from .opening_queue_budget import BrowserBudget
from .plan_promotion_catalog import VERSION, collection
from .plan_promotion_history import completed
from .unified_sources import resolve_source

IMMEDIATE = {
    "white": ("direct-white", "capture-white", "stalemate-white"),
    "black": ("direct-black", "capture-black", "stalemate-black"),
}


def _next(done):
    for color in ("white", "black"):
        if not any(key in done for key in IMMEDIATE[color]):
            return "direct-" + color, color, NOW
    for color in ("white", "black"):
        if "forced-" + color not in done:
            return "forced-" + color, color, FORCE
    return None


def recommendation(db, subject):
    try:
        with BrowserBudget(db).scope(snapshot=True):
            tasks = collection(db)
            chosen = _next(completed(db, subject, [item["task_id"] for item in tasks]))
            if chosen is None:
                return {"status": "complete"}
            key, color, objective = chosen
            source = resolve_source(db, "public", VERSION, key, subject=subject)
            if (source["learner_color"], source["objective"]) != (color, objective):
                raise ValueError("canonical promotion task changed")
            return {
                "status": "ready",
                "version": VERSION,
                "key": key,
                "color": color,
                "objective": objective,
            }
    except Exception:
        return {"status": "unavailable"}
