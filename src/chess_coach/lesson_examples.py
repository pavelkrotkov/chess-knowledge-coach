"""Choose bounded representative decisions from independent game identities."""

from .recurrence_context import context


def representatives(items, limit=10):
    seen, selected = set(), []
    for item in items:
        key = item["game_key"]
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            {
                **{name: item[name] for name in ("id", "game_id", "position_id", "ply")},
                "context": {
                    k: v
                    for k, v in context(item["decision"]).items()
                    if k in {"side", "phase", "clock", "time control"}
                },
            }
        )
        if len(selected) == limit:
            break
    return selected
