"""Keep one request and retain unresolved earlier intents."""

from .opening_queue_files import read
from .opening_study_request_validate import valid


def unchanged(old, item, database, learner, directory):
    if not old:
        return False
    if not valid(old, database, learner):
        raise ValueError("Study request unavailable")
    if (old["version"], old["selection"]) == (item["version"], item["selection"]):
        return old["state"] in {"queued", "complete"}
    intent = directory / f"opening-study-{old['version']}-intent.json"
    if intent.exists() and not read(intent).get("complete"):
        raise ValueError("Earlier Study request remains incomplete")
    return False
