# Material observation validation status

The independent curated validation supports only the pair
`material_protection`, detector version `1.0.0`, for possible eligibility. Its
success and preventable-loss failure were established for both colors. Current
protection witnesses may be exercise candidates with their actual review state:
unreviewed is explicitly provisional, accepted is reviewed, and rejected,
revoked, stale, ambiguous or unverified observations are excluded. Mastery also
requires an explicit human acceptance and all existing source, independent-game,
time and context checks. The source fact's exact kind, version, outcome and
operation must match; a mapping label cannot grant eligibility.

`material_capture` remains observation-only for all versions. Independent
validation established capture success for both colors but did not establish
black missed-capture failure or missed-capture failure on the owned-deep path
for either color. #187 remains mandatory to complete and separately validate
those outcomes. Missing or mismatched kinds and versions fail closed.

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
