"""Educational questions and practice habits for supported mechanisms."""

CUES = {
    "discovery-opportunity-mapper": (
        "Can moving one piece reveal a useful line from another?",
        "After considering the move, check both the moving piece and the newly revealed line, then test the defenses.",
        "Replay the linked decisions and compare the recorded legal replies.",
    ),
    "pin-execute-mapper": (
        "Can a slider pin a piece to its king or a more valuable piece?",
        "Check legal defenses and captures before relying on a pin.",
        "Replay the source and test each displayed defense and capture.",
    ),
    "pin-prevent-mapper": (
        "What happens if the pinned piece moves, or the pinning piece is captured?",
        "Compare legal defenses, checks and recaptures before moving.",
        "Replay the source and compare the tested pin and defensive alternatives.",
    ),
    "rook-plan-lesson-mapper": (
        "Which legal rook entry squares can be reached, and how can the opponent contest them?",
        "For each listed entry, calculate legal immediate captures and recaptures; compare the recorded alternative and inspect unchecked threats and later counterplay.",
        "Replay the linked decisions and test the recorded alternatives and immediate captures.",
    ),
    "king-safety-lesson-mapper": (
        "Which legal checks and king replies follow each choice?",
        "Compare the displayed legal checks, captures, and possible king replies before choosing.",
        "Replay the played move and alternative, and test the displayed checks.",
    ),
    "pawn-structure-lesson-mapper": (
        "Can the pawn advance safely, or can either side increase pressure or piece activity?",
        "Compare the pawn's legal advances, supporting pieces and immediate captures before choosing a plan.",
        "Replay the linked decisions, compare the recorded plans and counterplans, and check the displayed lines.",
    ),
    "material-opportunity-mapper": (
        "Could an exposed piece be captured, and what are the immediate replies?",
        "Before choosing a move, scan attacked pieces, possible captures and recaptures.",
        "Replay each linked decision, try the capture or defense, then compare the recorded lines.",
    ),
    "fork-opportunity-mapper": (
        "Can one move attack two valuable targets, and what defenses answer it?",
        "Look for moves that attack two targets, then check each forcing reply.",
        "Replay the linked decisions and try to find the fork before opening its source.",
    ),
    "fork-defense-mapper": (
        "After a candidate move, can the opponent attack two targets at once?",
        "Before moving, scan the opponent's checks, captures and double attacks.",
        "Replay the linked decisions, compare candidate defenses, and inspect their tested replies.",
    ),
    "bounded-mate-observation-mapper": (
        "Are there forcing checks that leave the king with no legal escape?",
        "When checks are available, examine replies and escape squares before deciding.",
        "Replay the linked decisions and try the proved mating choice before opening its proof.",
    ),
    "pawn-endgame-mapper": (
        "Which king or pawn moves preserve the proved result?",
        "Compare king activity, pawn promotion paths and the opponent's replies.",
        "Replay each linked position and compare your choice with its proved alternatives.",
    ),
    "back-rank-observation-mapper": (
        "Can a rook or queen reach the back rank, and does the king have a flight square?",
        "Before moving, scan back-rank threats and legal king flights for both sides.",
        "Replay the linked positions and test the displayed choices against the mate threats.",
    ),
}
