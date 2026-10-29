# Automatic bounded mate observations

The background pipeline scans learner decisions using an independent cursor and
limits. It always enumerates immediate legal mates, including equivalent mates.
It nominates a short search only when an immediate mate exists or the current
cheap best line reports mate for the mover within two moves. The score nominates
work; it never proves a claim. Other decisions are explicitly unknown for short
mates. Selected proofs use the existing 6,000-node, 100-reply and three-ply
limits; budget exhaustion is unknown. The worker reports its bounded scan and
outcome counts and revisits the backlog over subsequent ticks.

Current, separately versioned facts and provisional evidence record whether
played and alternative moves satisfy the bounded objective. A missed immediate
mate is factual even if another move also forces mate; the observation does not
infer the player's ability, intent, or psychological cause. Other wins beyond
the bound remain possible. The private evidence and mate pages show provenance,
limits, alternatives and stale or unknown status. Existing mate-v1 history is
not rewritten. The new family is explicitly excluded from mastery, including
when a fact is linked by a different mapper. Opening that gate requires an
independent held-out validation decision for the exact version.

The own-game practice adapter rechecks subject ownership, source currentness,
reviews and legal mating witnesses. It stores an immutable prepared-line snapshot
and preserves its source lineage. Unreviewed examples are provisional; rejected
or revoked examples are unavailable. Unlisted legal moves require verification,
and a completed prepared line is not a mastery assessment. Hints and explicit
reveals are durable assistance events. Back-rank defense remains issue #130;
generic live alternative grading remains #144.
