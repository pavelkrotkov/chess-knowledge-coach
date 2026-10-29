"""Mechanisms to investigate, separated from observations and diagnosis."""

MECHANISMS = {
    "discovery-opportunity-mapper": "A moving piece can uncover a slider, combining its newly revealed attack with the moving piece and its threats.",
    "pin-execute-mapper": "A possible mechanism is a slider restricting a piece because a king or more valuable piece lies behind it; verify the legal replies.",
    "pin-prevent-mapper": "A possible mechanism is a piece constrained by a slider, or a valuable piece exposed when it moves; verify the tested capture and defense.",
    "rook-plan-lesson-mapper": "A rook may use an open or half-open file for entry or pressure, but the position alone does not establish the best plan.",
    "king-safety-lesson-mapper": "Shelter changes can alter checks and king escapes; the displayed immediate replies do not establish overall safety.",
    "pawn-structure-lesson-mapper": "A possible mechanism is pressure on a pawn or activity supported by it; the position alone does not establish which plan is best.",
    "material-opportunity-mapper": "A possible local mechanism is an exposed piece being captured before it can be protected; check the replies in each source.",
    "fork-opportunity-mapper": "A possible local mechanism is a single move threatening two targets, so a defense of one can leave the other exposed.",
    "fork-defense-mapper": "A possible local mechanism is that a candidate move leaves two valuable targets vulnerable to one opposing move.",
    "bounded-mate-observation-mapper": "A possible local mechanism is a forcing check that leaves the king without a legal reply.",
    "pawn-endgame-mapper": "A possible local mechanism is that a king or pawn choice changes access to promotion or the opponent's ability to stop it.",
    "back-rank-observation-mapper": "A possible local mechanism is a rook or queen reaching the back rank while the king's flight squares are blocked or controlled.",
}
