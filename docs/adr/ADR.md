# ADR-001: Evidence-based mastery, never centipawn-loss mastery

Status: accepted (decided during the issues 1–10 build)

## Context

The obvious shortcut is to derive player skill directly from engine evaluations: more
centipawn loss = worse play. During implementation this was rejected because a
centipawn loss is not automatically a skill failure. A move can be slightly inferior
but chosen for practical reasons, or blundered for reasons (time pressure,
calculation, unknown pattern) that imply completely different training.

## Decision

Mastery conclusions are gated behind evidence:

- Engines and deterministic detectors produce **versioned facts** only.
- Facts become **evidence records** that preserve success, failure, and ambiguity —
  an opportunity with no outcome is recorded as ambiguous, never silently scored.
- Mastery aggregation requires multiple evidence contexts, human validation gating
  where appropriate, temporal weighting (recent games matter more), confidence/weight
  calculations, and stale-state invalidation.
- Every evidence fact carries provenance: detector version, mapper version, context,
  observation time.

## Consequences

- You cannot get a "player rating" out of one analyzed game; the system refuses.
- Detector/mapper upgrades recompute cleanly because versions are stored per fact.
- Raw game data stays immutable; all interpretation is revisable downstream data.

# ADR-002: Deterministic-first, LLM-last

Status: accepted

## Context

LLMs are tempting for both detection ("is this a fork?") and explanation. Detection
by LLM is non-reproducible and unverifiable; explanations that touch canonical state
would let model output contaminate chess truth.

## Decision

- Structure/motif detection is **deterministic code** with versioned detectors
  (`structures.py`, `motifs.py`). Same board in, same versioned facts out, always.
- Skill mapping from detector facts goes through a versioned ontology + mapper
  (`ontology.py`), also deterministic.
- The LLM appears in exactly two places, both optional and sandboxed:
  1. **Maia adapter** — subprocess returning rating-conditioned human-move
     probabilities; strict validation (JSON object, finite [0,1] probabilities),
     Elo conditioning stored with predictions, required reproducible checkpoint IDs;
     offline mode returns nothing rather than approximating.
  2. **Explanation adapter** — receives serialized facts/evidence only, writes to
     separate provenance tables, and structurally cannot mutate canonical state.

## Consequences

- All analysis is recomputable and auditable end-to-end.
- LLM unavailability degrades enrichment only, never the core pipeline.
- Adding any new "smart" feature requires justifying why it cannot be deterministic.

# ADR-003: Atomic imports and analysis merges

Status: accepted

## Context

Bulk workflows (analyze on newer hardware, import large puzzle corpora) fail midway:
truncated CSVs, HTTP interruptions, missing games on merge. Naive imports leave
partial state or crash with raw sqlite errors.

## Decision

- Corpus/dataset imports validate every row up front (required fields, row numbers in
  errors) and roll back completely on failure; missing optional columns are tolerated
  as empty strings, truncated rows abort the import with a clear message.
- `merge_analysis_outputs(target_db, source_db)` maps games by `(source, source_id)`
  and positions by `(game_id, ply)`, remaps foreign keys, and commits atomically;
  any missing stable identity aborts the entire import.
- Opening dataset imports support transposition-aware DAG classification with atomic
  rollback and stable dataset resolution by version.

## Consequences

- A failed run never leaves half-imported data; retry is always safe.
- Error messages point at the offending row instead of leaking SQL internals.

# ADR-004: Reproducible engine configuration and bulk-analysis handoff

Status: accepted

## Decision

- Engine runs persist full identity: binary path, engine name/version, NNUE files,
  and complete config (nodes, depth, MultiPV, threads, hash). Missing or
  unstartable binaries fail loudly.
- POPCNT vs generic x64 compatibility is detected; the 2010 Mac mini does
  ingestion/reporting only, heavy Stockfish/Maia batches run elsewhere and merge
  back via the atomic merge helper.
- FSRS scheduler versioning derives from the installed package so scheduling
  behavior changes are visible in history.

# ADR-005: Provenance over conclusions everywhere

Status: accepted

## Decision

Every persisted derived value carries: source identity, version(s) of everything
that produced it, timestamp, and enough raw input to recompute. Tables keep raw
fields (raw PGN, raw descriptors) alongside normalized ones. Nothing opaque is
stored: if a number appears in a report, its lineage is queryable.

## Consequences

Reproducibility is structural, not aspirational; debugging is done by querying
lineage rather than reading logs.
