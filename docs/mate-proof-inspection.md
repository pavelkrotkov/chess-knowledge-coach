# Private bounded mate inspection

`chess-coach inspect-mate POSITION_ID` and the private decision page's mate link
inspect one learner-owned decision from the current completed cheap-analysis
checkpoint. The learner identity must match the mover. A missing, changed, or
unattributable source is unavailable; a supplied `--source-fingerprint` (or
browser `source` query parameter) reports stale when it no longer matches. The
fingerprint identifies the source and proof version, including its analysis run;
the result is computed on demand and is not persisted as evidence. The source
is checked again after computing. Legacy mate evidence and reviews are unchanged.

The tool reconstructs the game, validates its recorded moves, enumerates every
legal immediate checkmate, and separately reports the actual played checkmate,
stalemate, or immediate mate not played. These facts say nothing about intent or
mastery. Standard chess and at most 1,000 recorded plies are supported.

For mate in at most two moves, the shared budget is 6,000 visited search
positions and at most 100 legal replies at any defender position, with a maximum
of three plies. Immediate-mate enumeration is separate and bounded by the legal
root moves. Each proved root includes one legal mating reply for every legal
defender move. Automatic draws and a defender's available draw claim prevent a
forced proof. Checkmate takes precedence when it has already occurred. A root
is disproved only when a legal defense refutes that bounded objective; an
exhausted node or reply budget is unknown. When any root is proved, the overall
result is proved even if other alternatives are unknown; inspect each root's
status to see whether the alternative search completed. Proofs are not engine
scores or principal variations. This is an on-demand CPU-bound search, not a
wall-clock deadline, automatic backfill, exercise grader, or evidence producer.

Family eligibility, automatic coaching and back-rank integration remain pending
independent validation under #130. Alternative-aware session grading belongs to
#144. No short-mate observation from this tool updates mastery or training.
