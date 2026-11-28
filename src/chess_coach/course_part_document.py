"""Serialize one part while binding its parent, indices and exact chapters."""

from .course_preview import preview_hash


def build(items, parent, number, packed):
    chapters = [item[2] for item in items]
    part = {
        "parent_sha256": parent,
        "number": number + 1,
        "count": len(packed),
        "indices": [item[0] for item in items],
        "chapters": chapters,
        "pgn": "\n\n".join(chapter["pgn"] for chapter in chapters) + "\n",
        "continues_previous": number > 0 and packed[number - 1][-1][1] == items[0][1],
        "continues_next": number + 1 < len(packed) and items[-1][1] == packed[number + 1][0][1],
    }
    return {**part, "sha256": preview_hash(part)}
