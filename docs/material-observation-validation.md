# Material observation validation status

Independent curated validation supports `material_protection` detector version
`1.0.0` and `material_capture` detector version `1.1.0` for possible eligibility.
The protection family is restricted to `hanging_piece` / `prevent`; its
success and preventable-loss failure were established for both colors. Current
protection witnesses may be exercise candidates with their actual review state:
unreviewed is explicitly provisional, accepted is reviewed, and rejected,
revoked, stale, ambiguous or unverified observations are excluded. Mastery also
requires an explicit human acceptance and all existing source, independent-game,
time and context checks. The source fact's exact kind, version, outcome and
operation must match; a mapping label cannot grant eligibility.

The capture approval is restricted to `hanging_piece` / `execute` and factual
`success` or `failure`; it requires the exact producer, fact type and matching
fact/run detector version. The same subject, review, source currentness, time
and independent-context gates apply. Current unreviewed exercise candidates are
visibly provisional; rejected, revoked, stale and unverified sources are excluded.
Capture version `1.0.0`, unknown or mismatched versions and other operations
remain ineligible.

For a missed capture, the candidate is the current engine best root, not an
exhaustive search of all legal captures; a quiet best root can therefore leave a
real capture outside coverage. Capture detector version `1.1.0` permits a
checking reply in the recorded played line when a legal continuation resolves
the check within eight plies. Ordinary played lines retain their original
four-ply comparison; a checking continuation is evaluated for at least four
plies. A checking played alternative remains ambiguous, and the candidate still
has to pass its bounded legal-reply proof, exact score veto and concrete material
comparison. A recorded line is not a proof against later counterplay. The
protection detector remains at its independently validated version `1.0.0`. Old
capture facts are superseded on reprocessing without deleting their reviews.
Independent validation and a separate eligibility decision now cover this narrow
scope; wider capture claims remain unvalidated.

A fresh, separately sealed 24-case independent evaluation at commit `5f96b21`
used complete current owned-deep sources for every case, with both roles qualified,
no cheap fallback, no worker caps and no errors. The 12 intended positives yielded
cheap four capture successes, five capture failures, one ambiguous and two
protection successes; deep yielded two capture successes, five capture failures,
three ambiguous and two protection successes. Deep capture results include White
one success and two failures, Black one success and three failures. All 12
negative/exclusion controls remained ambiguous on both paths: two each covered
recapture, queen sacrifice, pawn target, checking played alternative, promotion
and en passant. One positive was ambiguous on both paths due to a forcing reply;
two bishop-captures-rook successes were supported cheaply but ambiguous in deep
because the recorded played PV contained only its root. The two protection
successes use the separately approved protection version. These curated counts
are not an accuracy estimate. See the [independent decision](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/187#issuecomment-6490272316).

The previous independent evaluation did not establish black missed captures or
owned-deep missed captures, leading to the mandatory #187 continuation. Its
preserved results follow.

The fresh 44-case set plus a separately sealed ten-case supplement comprise 54
curated cases: cheap analysis produced 13 success, three failure and 38
ambiguous results. The 30 intended positive cases were also tested through
owned-deep analysis, producing 12 success, two failure and 16 ambiguous.
Eight positive cases were independently adjudicated outside the declared scope
(defended or recapturable), leaving 22 ordinary in-scope positives: cheap
supported 16 and left six ambiguous; deep supported 14 and left eight
ambiguous. All 24 negative/ambiguous controls remained ambiguous, with no
unsupported decisive claims found. Source, replay, review, atomic race and
stale-browser checks passed. These curated results are not accuracy estimates.
The per-category in-scope results are:

| Category | Cases | Cheap: success / failure / ambiguous | Deep: success / failure / ambiguous |
| --- | ---: | ---: | ---: |
| Executed non-pawn capture, including equivalent roots and legal pinned defenders | 8 | 8 / 0 / 0 | 8 / 0 / 0 |
| Missed capture | 4 | 0 / 1 / 3 | 0 / 0 / 4 |
| Quiet protection | 4 | 3 / 0 / 1 | 2 / 0 / 2 |
| Capture of an unrecapturable pawn attacker | 2 | 2 / 0 / 0 | 2 / 0 / 0 |
| Ignored preventable immediate loss | 4 | 0 / 2 / 2 | 0 / 2 / 2 |

For supported protection, White had cheap 2 success / 2 failure and deep
2 success / 1 failure; Black had cheap 3 success / 0 failure and deep 2 success /
1 failure. Deep reused the 30 positive positions, not 30 additional independent
cases: 29 used owned-deep and one used a cheap fallback within the excluded eight,
so all 22 in-scope positives used owned-deep. Cheap limits were 10,000 nodes and
0.25 seconds per role; deep limits were 50,000 nodes and 0.5 seconds, one thread
and 16 MiB hash. The excluded eight were four profitable defended exchanges,
two protective captures with legal recapture, and two captures while already
in check with recapture. The last two do not validate universal checking-capture
behavior.

An earlier separate 28-case evaluation had 25 ambiguous, two failure and one
success; its weak coverage motivated the correction and is not pooled into the
54 cases.

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
tactics. Direct pawn-capture claims, en passant, promotions, unresolved checks or evasions,
illegal or pinned pseudo-attacks, exhausted bounds, unclear exchanges, mate or
bounded scores, insufficient PVs, conflicting lines and possible material
compensation remain ambiguous or outside coverage. Protection may include a pawn
capturing an unrecapturable attacker. For a possible failure, an
exact same-board score gap is used only as a conservative veto for conflicting
engine assessments; the gap alone never creates an observation or evidence.
The fixed mapping confidence is an uncalibrated placeholder, not an empirical
probability. Every mapping is unreviewed on creation. A human review is recorded
separately and does not override the kind/version, currentness or context gates.
