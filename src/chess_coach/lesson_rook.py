"""Present recorded rook choices and their immediate legal capture checks."""

from .lesson_adapter_common import line


def _root_facts(role, root):
    if root is None:
        return [f"After {role}, the tracked rook is unavailable."]
    check = root["captures"]
    if check["status"] != "checked":
        return [f"After {role}, immediate captures of the rook on {root['square']} are unresolved."]
    captures = check["captures"]
    if not captures:
        return [f"After {role}, no immediate legal capture of the rook on {root['square']} exists."]
    return [
        f"After {role}, {item['san']} captures the rook on {root['square']}; the bounded exchange gains {item['gain']} material units for the capturing side."
        for item in captures
    ]


def rook(evidence, fen):
    payload = evidence["facts"][0]["payload"]
    facts = [
        f"The {payload['color']} rook on {payload['rook']} has a recorded move to the {payload['file']}-file, which is {payload['file_kind']} in the source position.",
        payload["plan"],
        f"Counterplan: {payload['counterplan']}",
    ]
    entries = payload["entries"]
    if entries:
        facts.append(
            "Legal rook moves into the enemy half on open or half-open files: "
            + ", ".join(item["san"] for item in entries)
            + "."
        )
    else:
        facts.append(
            "No legal rook move enters the enemy half on an open or half-open file in the source position."
        )
    for item in entries:
        facts.extend(_root_facts(f"legal entry {item['san']}", item))
    for role, root in payload["roots"].items():
        facts.extend(_root_facts(f"the {role} recorded root", root))
        if root:
            squares = root["rook_attacks_enemy_half"]
            facts.append(
                f"After the {role} recorded root, the mover's rooks geometrically attack {len(squares)} enemy-half squares: {', '.join(squares) or 'none'}. This includes occupied squares and attacks by pinned rooks; it does not establish legal moves or recaptures."
            )
    lines = [
        line(fen, f"Recorded {role}-search continuation", item["san"])
        for role, item in payload["lines"].items()
    ]
    return facts, lines
