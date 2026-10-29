# Pawn-structure lesson qualification decision

Decision: **not qualified for mastery**. Version 1.1.0 publishes only ambiguous
descriptive mappings, including when a continuation contains a capture or an
immediate alternative has a different target-square exchange. This is a closed
gate, including for accepted reviews. A review of one observation is not family
validation. No execution, prevention, intent, position evaluation or failure is
inferred from the geometry, a score or a single engine continuation.

An [independent review](https://github.com/pavelkrotkov/chess-knowledge-coach/pull/213#pullrequestreview-5699254141)
of version 1.0.0 examined eight held-out cases: three
positive, two negative and three ambiguous, with zero false bounded pawn-capture
claims. That review did not qualify compensation, forcing claims or mastery.
Version 1.1.0 adds supported-piece activity comparisons; no independent held-out
review of these new claims has yet been completed. This is a disclosure, not a
qualification result. Before opening the gate, a reviewer independent of
implementation must assess a separate held-out set, report the counts and false
claims, and document a qualification decision with the supported boundaries.
Unsupported cases remain visible as unknown. No such approval is implied here.

Development tests use synthetic positions, including both-color supported-piece
exchange comparisons and pinned-pawn counterexamples, scan-budget and stale-source
replay checks, and a version
upgrade with preserved review history. Other cases include: a direct isolated-pawn capture,
a legal alternative that changes the immediate exchange, a color mirror,
backward-pawn geometry and capture, an isolated pawn supporting an active
knight, missing and illegal continuations, review replay, source supersession
and a closed mastery gate. They are not a held-out accuracy set.
Beneficial isolated pawns and activity compensation must not be called failures;
the present detector does not assess positional compensation or prove a plan is
universally useful. Capture exchanges test recaptures only on one square, not
all replies or later tactics. An engine line shows a legal possibility, not a
forced consequence.
