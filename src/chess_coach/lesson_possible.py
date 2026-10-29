"""Mechanisms to investigate, separated from observations and diagnosis."""

MECHANISMS = {
    "material-opportunity-mapper": "A possible local mechanism is an exposed piece being captured before it can be protected; check the replies in each source.",
    "fork-opportunity-mapper": "A possible local mechanism is a single move threatening two targets, so a defense of one can leave the other exposed.",
    "fork-defense-mapper": "A possible local mechanism is that a candidate move leaves two valuable targets vulnerable to one opposing move.",
    "bounded-mate-observation-mapper": "A possible local mechanism is a forcing check that leaves the king without a legal reply.",
    "pawn-endgame-mapper": "A possible local mechanism is that a king or pawn choice changes access to promotion or the opponent's ability to stop it.",
    "back-rank-observation-mapper": "A possible local mechanism is a rook or queen reaching the back rank while the king's flight squares are blocked or controlled.",
}
