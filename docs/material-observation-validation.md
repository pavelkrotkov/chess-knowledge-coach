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
and replays two or four plies of the current, same-board engine continuations.
It does not prove the position is winning, rule out every non-capturing tactic,
or assess the reasoning of the learner. The opponent-turn protection probe is a
hypothetical immediate-move check, not an actual game continuation; it is used
only when the board is valid, neither side is in check, no en passant right is
present and repetition/fifty-move boundaries do not apply. Actual line claims
require the recorded legal played continuation.

Pawn captures, en passant, promotions, checks and forcing checking alternatives,
illegal or pinned pseudo-attacks, exhausted bounds, unclear exchanges, mate or
bounded scores, insufficient PVs, conflicting lines and possible material
compensation remain ambiguous or outside coverage. For a possible failure, an
exact same-board score gap is used only as a conservative veto for conflicting
engine assessments; the gap alone never creates an observation or evidence.
The fixed mapping confidence is an uncalibrated placeholder, not an empirical
probability. Every mapping is unreviewed on creation. A human review is recorded
separately and does not override the validation gate.
