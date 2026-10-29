# Provisional pawn-endgame coaching

The bounded pipeline runs a separate pawn worker over learner-owned positions
with current completed analysis. It reconstructs the original game history,
uses the pinned local proof from [pawn-endgame inspection](pawn-endgame-inspection.md),
and atomically records versioned facts and unreviewed mappings. It never sends
positions to an outside service. Unsupported roots are skipped; a previous
pawn run is superseded if a source becomes unsupported. Unknown history, a
missing proof resource, a capped proof, or unresolved alternatives are reported
as ambiguous rather than as a loss.

A meaningful opportunity requires a proved root win or draw, at least one
legal alternative with that exact result, and at least one legal alternative
with a strictly worse exact result. A proved preserving played move is a
provisional success; a proved worse played move is a provisional failure. A
forced losing position, a forced move, uniformly equivalent choices, unknown
played result, or absence of a verified contrast is ambiguous. Other legal
moves remain unknown when their bounds do not coincide. En passant, captures,
double pushes, promotion alternatives and draw claims follow the underlying
history-aware proof. No result is inferred from geometry, a pawn reaching the
last rank, engine score, intent or playing strength. The operation is execute
for a root win, prevent for a root draw and evaluate when unresolved.

Each fact includes the proof and the source fingerprint, and consumes the proof
version, manifest hash and proof digest. Publication rechecks the current
source and resource availability inside its transaction. Replaying unchanged
inputs retains the original review state; changed source or proof creates a
new run and mapping, supersedes the old one without deleting history, and never
transfers an acceptance. The evidence page recomputes the bounded proof and
checks the active mapping, link, consumed inputs and source before presenting
its explanation; stale information is identified as historical. The explanation
shows proved one-move alternatives, the position's objective and descriptive
straight-ahead promotion squares. Those are not a complete forced line, and
pawn captures may change the promotion file.

The worker uses its own cursor and defaults to at most 40 scanned positions
and four supported decisions per invocation, configurable with
`--pawn-max-scan`, `--pawn-max-decisions`, and `--no-pawn`. Each decision has
the proof's shared 6,000-node, five-ply ceiling; no wall-clock guarantee is
implied. Worker output contains counts and sanitized statuses, not game
contents. The private library checks at most one recent source reference per
page without rerunning its mathematical proof and links to the next page; each
reference remains provisional until explicitly verified at session start. The
CLI exposes the same cursor through
`list-pawn-practice --subject SUBJECT --before ID`. A bounded in-process cache
reuses only a verified mathematical proof for identical position history, limits,
version and manifest. Every access rechecks the local resource bytes, subject,
source, fact lineage and current review; restarting a process clears the cache.
The first verification when starting or reopening an uncached session can take seconds.

Own-game exercises are available provisionally when the proof and source are
current and review is unreviewed or accepted. Rejected, revoked, changed or
unavailable sources cannot start or continue an attempt. Prepared sessions
contain only verified preserving moves as supplied one-move lines. Completing a
line does not claim the broader objective has been independently graded; an
unlisted legal move needs verification and is not failed. Generic
alternative-aware grading remains #144. Candidates can be practiced before
family qualification, but they cannot produce mastery evidence. The browser
states this distinction, including for individually reviewed observations.

Game-derived `king_pawn_endgame` and `promotion` evidence is explicitly closed
to mastery regardless of mapper name. A pawn mapper or a linked pawn detector
fact also stays closed if relabeled under another skill. This does not alter
the separate independently verified training path. A fresh independent held-out
positive, negative and ambiguous qualification of the final detector, mapper,
source checks and practice behavior, with counts and false claims, is required
before any pawn game-derived family/version can become mastery-eligible. No
qualification, human review, practice attempt or mastery is fabricated by the
worker.
