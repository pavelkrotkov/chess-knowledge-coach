# Material observation validation status

The `material-opportunity` detector version 1.0.0 is **not mastery eligible**.
The eligibility registry intentionally contains no approved material version;
even a human-accepted mapping remains excluded until an independent held-out
positive, negative and ambiguous evaluation is completed, its false claims and
counts are documented, and an explicit version-specific decision is recorded.
No held-out evaluation has been performed in this implementation.

The supported observation is a narrow, provisional description of a concrete
non-pawn capture or an immediate protection opportunity. The verifier considers
legal captures and recaptures on one square for at most six plies and 64 nodes,
and replays short same-board engine continuations: ordinarily two or four
plies, with up to eight plies to obtain a legal response to a displayed check.
An individually verified played line from a current incomplete deep attempt
may support a played success without borrowing an unrelated cheap best line.
It does not prove the position is winning, rule out every non-capturing tactic,
or assess the reasoning of the learner. The opponent-turn protection probe is a
hypothetical immediate-move check, not an actual game continuation; uncertainty
is scoped to the threatened piece, and a move that newly exposes other material
remains ambiguous. It is used
only when the board is valid, neither side is in check, no en passant right is
present and repetition/fifty-move boundaries do not apply. Actual line claims
require the recorded legal played continuation.

For an ordinary capture, up to 64 legal immediate replies are checked for
checks, promotions, draws and captures that erase the material gain; exceeding
the bound is ambiguous. A checking capture is supported only when every legal immediate evasion is
examined within a 64-reply cap, none captures material or counterchecks, and
each preserves the bounded material gain; this is not proof against later
tactics. Pawn captures, en passant, promotions, unresolved checks or evasions,
illegal or pinned pseudo-attacks, exhausted bounds, unclear exchanges, mate or
bounded scores, insufficient PVs, conflicting lines and possible material
compensation remain ambiguous or outside coverage. For a possible failure, an
exact same-board score gap is used only as a conservative veto for conflicting
engine assessments; the gap alone never creates an observation or evidence.
The fixed mapping confidence is an uncalibrated placeholder, not an empirical
probability. Every mapping is unreviewed on creation. A human review is recorded
separately and does not override the validation gate.
