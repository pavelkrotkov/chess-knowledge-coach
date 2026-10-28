"""Select distinct prompts with transparent supporting reasons."""


def select(
    candidates: list[dict], limit: int, summary: dict, seen: set[str]
) -> tuple[list[dict], set[str]]:
    selected = []
    for candidate in candidates:
        if len(selected) >= limit:
            break
        if candidate["prompt_key"] in seen:
            continue
        seen.add(candidate["prompt_key"])
        selected.append(
            {
                **candidate,
                "reason": _reason(candidate, summary),
                "evidence_ref": "mate_in_one" if summary["supporting_evidence_ids"] else None,
            }
        )
    return selected, seen


def _reason(candidate: dict, summary: dict) -> str:
    if candidate["kind"] == "due":
        return "Scheduled puzzle review is due."
    if summary["state"] == "supported_weakness":
        return "Verified practice targets a supported mate-in-one weakness."
    if summary["state"] == "cold_start":
        return "Verified practice for a cold start; no weakness is inferred."
    if summary["state"] == "insufficient_evidence":
        return "Verified practice while reviewed evidence is insufficient."
    if summary["state"] == "evidence_scan_incomplete":
        return "Verified practice; the bounded evidence scan is incomplete."
    return "Verified practice; no supported weakness is inferred."
