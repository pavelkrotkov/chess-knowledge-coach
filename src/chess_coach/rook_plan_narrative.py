"""Ground conditional plans in saved legal roots and immediate exchange checks."""


def _unsupported(move, square, alternative, reply):
    return {
        "plan_status": "unsupported",
        "plan": f"No supported plan is established for {move} to {square}: immediate captures are unresolved. Compare the recorded alternative {alternative}.",
        "counterplan": f"A concrete capture counterplan after {move} is unresolved. The recorded line replies {reply}, but its strategic effect is not established.",
        "next": f"Before choosing {move}, investigate checks and captures and compare {alternative}; the immediate exchange check was inconclusive.",
    }


def _no_capture(move, square, alternative, reply, destination):
    return {
        "plan_status": "immediate_capture_absent",
        "plan": f"Consider {move} to {square} as {destination}; no immediate legal capture of that rook was found. Compare the recorded alternative {alternative}.",
        "counterplan": f"The recorded line replies {reply}; whether it contests {square} or creates a later threat is unverified. No immediate capture counterplan was found.",
        "next": f"After {move}, inspect {reply}, other checks and threats, and later captures; compare these with {alternative} before choosing.",
    }


def _capture(move, square, alternative, capture, destination):
    reply, gain = capture["san"], capture["gain"]
    return {
        "plan_status": "immediate_capture_found",
        "plan": f"Compare {move} to {square} as {destination} with {alternative}: the legal reply {reply} has a bounded exchange gain of {gain} material units for the capturing side.",
        "counterplan": f"After {move}, the opponent can capture with {reply}; the bounded exchange gains {gain} material units for that side. This reply is possible, not forced.",
        "next": f"After {move}, calculate {reply} and its legal recaptures, then compare {alternative} and threats beyond this exchange.",
    }


def narrative(roots, lines, entries, role):
    root, line = roots[role], lines[role]
    move, reply = line["san"][:2]
    alternative = lines["played" if role == "best" else "best"]["san"][0]
    square = root["square"]
    destination = (
        "an enemy-half entry" if any(item["san"] == move for item in entries) else "file occupation"
    )
    check = root["captures"]
    if check["status"] != "checked":
        return _unsupported(move, square, alternative, reply)
    if not check["captures"]:
        return _no_capture(move, square, alternative, reply, destination)
    capture = max(check["captures"], key=lambda item: item["gain"])
    return _capture(move, square, alternative, capture, destination)
