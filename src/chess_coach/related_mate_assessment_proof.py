"""Prove roots and all defensive replies within one shared budget."""

from .mate_practice_defenses import defense_lines
from .mate_proof import MAX_NODES, Budget, _root
from .mate_proof import VERSION as PROOF_VERSION
from .related_mate_assessment import VERSION, setup


def certificate(db, version, key):
    board, moves, fingerprint = setup(db, version, key)
    supplied = board.parse_uci(moves[1])
    budget = Budget(MAX_NODES)
    roots = _roots(board, supplied, budget)
    return {
        "version": VERSION,
        "proof_version": PROOF_VERSION,
        "node_limit": MAX_NODES,
        "nodes": budget.nodes,
        "history_mode": "zeroing_setup",
        "source_fingerprint": fingerprint,
        "roots": roots,
        "lines": _lines(board, roots),
    }


def _roots(board, supplied, budget):
    first = _root(board, supplied, budget)
    if first["status"] != "proved" or first["distance_plies"] != 3:
        raise ValueError("assessment supplied root is not proved")
    roots = [first]
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        if move == supplied or budget.nodes >= MAX_NODES:
            continue
        proof = _root(board, move, budget)
        if proof["status"] == "proved" and proof["distance_plies"] == 3:
            roots.append(proof)
    return roots


def _lines(board, roots):
    lines = []
    for proof in roots:
        move = board.parse_uci(proof["move"]["uci"])
        board.push(move)
        try:
            lines.extend(defense_lines(board, proof, move))
        finally:
            board.pop()
    return lines
