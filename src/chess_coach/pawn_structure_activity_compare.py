"""Compare the same immediate capture after two legal recorded roots."""


def comparison(roots):
    best, played = roots["best"], roots["played"]
    if best is None or played is None:
        return None
    if (best["status"], played["status"]) != ("checked", "checked"):
        return None
    if (len(best["captures"]), len(played["captures"])) != (1, 1):
        return None
    first, second = best["captures"][0], played["captures"][0]
    if first["san"] != second["san"] or first["gain"] == second["gain"]:
        return None
    return {"capture": first["san"], "best_gain": first["gain"], "played_gain": second["gain"]}
