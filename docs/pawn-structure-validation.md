# Pawn-structure lesson qualification decision

Decision: **not qualified for mastery**. Version 1.0.0 publishes only ambiguous
descriptive mappings, including when a continuation contains a capture or an
immediate alternative has a different target-square exchange. This is a closed
gate, including for accepted reviews. A review of one observation is not family
validation. No execution, prevention, intent, position evaluation or failure is
inferred from the geometry, a score or a single engine continuation.

No independently reviewed held-out positive, negative or ambiguous cases have
been submitted for this version: counts 0 / 0 / 0; false claims have not been
measured. These zero counts are a disclosure, not a validation result. Before
opening the gate, a reviewer independent of implementation must assess a
separate held-out set, report the counts and false claims, and document a
qualification decision with the supported boundaries. Unsupported cases remain
visible as unknown. No such approval is implied here.

Development tests use synthetic positions: a direct isolated-pawn capture,
a legal alternative that changes the immediate exchange, a color mirror,
backward-pawn geometry and capture, an isolated pawn supporting an active
knight, missing and illegal continuations, review replay, source supersession
and a closed mastery gate. They are not a held-out accuracy set.
Beneficial isolated pawns and activity compensation must not be called failures;
the present detector does not assess positional compensation or prove a plan is
universally useful. Capture exchanges test recaptures only on one square, not
all replies or later tactics. An engine line shows a legal possibility, not a
forced consequence.
