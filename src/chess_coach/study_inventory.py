"""Find only the uniquely marked Study belonging to the authenticated account."""

import json
from urllib.parse import quote

from .study_privacy import chapter_mode
from .study_remote import StudyError


def inventory(remote, account, marker):
    name = quote(account["username"], safe="")
    response = remote.request("GET", "/api/study/by/" + name)
    try:
        studies = [json.loads(line) for line in response.text.splitlines() if line]
        return [row["id"] for row in studies if row.get("name") == marker]
    except (ValueError, KeyError, TypeError):
        raise StudyError("Study inventory could not be verified") from None


def verify_chapters(study, state, chapters):
    items = study.get("chapters")
    if not isinstance(items, list) or not any(
        item.get("id") == state["empty_chapter"] for item in items
    ):
        raise StudyError("initial Study chapter is unavailable")
    if chapters is not None and len(items) != len(chapters) + 1:
        raise StudyError("Study chapter inventory is incomplete")


def named(chapter, state, index):
    return {**chapter, "name": f"{chapter['title']} [{state['marker'][-16:]}-{index + 1}]"}


def verify_modes(remote, study, state, chapters):
    for i, chapter in enumerate(chapters):
        name = named(chapter, state, i)["name"]
        found = [item["id"] for item in study["chapters"] if item.get("name") == name]
        if len(found) != 1:
            raise StudyError("chapter identity could not be verified")
        chapter_mode(remote, state["study"], found[0])
