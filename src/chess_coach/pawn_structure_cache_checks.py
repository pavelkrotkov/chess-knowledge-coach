"""Check cached mapping interpretation against the saved source."""


def content_matches(data, inputs, detector_run, payloads, context, game_id):
    details = {
        "game_id": game_id,
        "ply": context["ply"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
        "lesson": payloads[0]["payload"] if payloads else None,
        "provenance": inputs["provenance"],
    }
    return (
        data["source"] == inputs
        and data["fact_run"] == detector_run["id"]
        and data["context"] == details
    )


def mapped_matches(mapped, details):
    if mapped is None:
        return False
    if not mapped:
        return True
    return (
        mapped[0]["outcome"] == "ambiguous"
        and mapped[0]["skill"] == "pawn_structure"
        and mapped[0]["context"] == details
    )
