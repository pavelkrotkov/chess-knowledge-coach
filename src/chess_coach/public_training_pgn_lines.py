"""Enumerate explicitly supplied, bounded PGN variation lines."""


def pgn_lines(game):
    stack = [(game, [])]
    lines = []
    while stack:
        node, moves = stack.pop()
        if not node.variations:
            lines.append(" ".join(moves))
            if len(lines) > 16:
                raise ValueError("too many PGN lines")
        for child in reversed(node.variations):
            if len(moves) >= 64:
                raise ValueError("PGN line too long")
            stack.append((child, [*moves, child.move.uci()]))
    return lines
