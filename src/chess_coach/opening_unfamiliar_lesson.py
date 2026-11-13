"""Build one sourced exploratory opening lesson and its checked PGN."""

from .course_pgn import chapter
from .opening_unfamiliar_binding import binding


def _scope(report, item):
    coverage, public = report["coverage"], item["profile"]["coverage"]
    limit = "The 100-game limit was reached. " if coverage["game_limit_reached"] else ""
    tie = "Games tied at the boundary may be omitted. " if coverage["boundary_tie"] else ""
    truncated = "The archive scan was truncated. " if public["truncated"] else ""
    return (
        f"The recent sample contains {report['sample']} verified games. "
        f"The first turns of {report['white_count']} White and {report['black_count']} Black "
        f"games were checked. {report['failed']} could not be checked. {limit}{tie}"
        f"At least {coverage['unknown_time_lower_bound']} games lack a verified start time, "
        f"and at least {coverage['unknown_ownership_global_lower_bound']} have uncertain ownership. "
        f"The sample recheck failed for {coverage['candidate_recheck_failed']} candidates, "
        f"including {coverage['oversized_pgn']} oversized games. "
        f"The public sample accepted {public['accepted']} of {public['examined']} examined games. "
        f"It excluded {public['excluded']}, had {public['duplicates']} duplicates and "
        f"{public['unknown_context']} games with missing context. {truncated}"
    ).strip()


def _geometry(data):
    shapes = (
        ", ".join(
            f"{shape['name']} for {shape['color']} in {shape['count']}"
            for shape in data["families"]
        )
        or "no supported named geometry"
    )
    center = data["center"]
    more = "More matching games were available. " if data["more_matches"] else ""
    return (
        f"Among {data['games']} selected public games, the observed geometry was {shapes}. "
        f"The sample uses at most ten matches and twelve post-move positions per game. {more}"
        f"Of {center['valid']} checked four-ply windows, {center['capture']} included a "
        f"central pawn capture and {center['opened_any']} opened a d or e file. "
        f"{data['no_supported_match']} games had no supported named geometry and "
        f"{data['short_windows']} had shorter windows."
    )


def lesson(report, color, item):
    line, data = item["line"], item["profile"]
    snapshot, provenance = binding(report, color, item)
    source = provenance["source_url"]
    parent = (
        f" Against {report['parent']}, the common checked first move in "
        f"{report['parent_count']} Black games."
        if color == "black"
        else ""
    )
    reason = (
        f"Exploratory: {item['name']} ({item['eco']}). This legal catalog move was not found "
        "among your indexed imported first-turn choices and has a checked public example."
        f"{parent} Style compatibility and engine soundness are unknown."
    )
    instruction = (
        f"Play {line['san'][0]}. After {line['san'][1]}, pause and choose your next move "
        "before revealing the recorded continuation."
    )
    revisit = "Revisit from this position later without looking, then compare your choices with the recorded line."
    scope, geometry = _scope(report, item), _geometry(data)
    attribution = (
        f"Opening catalog: {report['catalog_source']} (CC0). Public source: {source}. "
        f"Archive record {line['record']}. {data['license']}: {data['license_url']}. "
        f"Archive SHA-256: {data['source_sha256']}."
    )
    note = (
        f"Play {color.title()}. {reason} {instruction} {revisit} {scope} {geometry} {attribution}"
    )
    result = chapter(item["name"], note, snapshot, provenance, guidance=note)
    return {
        **result,
        "color": color,
        "name": item["name"],
        "eco": item["eco"],
        "note": note,
        "reason": reason,
        "instruction": instruction,
        "revisit": revisit,
        "scope": scope,
        "geometry": geometry,
        "san": line["san"],
        "fen": line["fen"],
        "source_url": source,
        "license": data["license"],
        "license_url": data["license_url"],
    }
