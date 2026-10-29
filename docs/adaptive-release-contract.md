# Adaptive coach release contract

The [release issue #119](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/119)
is the completion gate. This contract records what must be demonstrated, not a
claim that those features already work. The versioned `capabilities` CLI report
and private browser page are the source of truth for current coverage. Status
means **supported** for the stated scope, **observation-only** for descriptive
facts without reliable skill outcomes, or **planned** for work not yet delivered.
Update the registry and its behavioral tests in the same change as each feature.
Capability IDs are stable; increase the registry version when its meaning changes.

## Original-vision audit

The original [knowledge graph vision](../kg.md) calls for reproducible game facts,
opportunities and reviewed evidence, adaptive skill learning, own and public
practice, grounded coaching, opening/style/structure context, and personalized
courses. Ingestion, bounded engine scans, structures, opening classification,
versioned evidence and review, mastery-v2, FSRS, and a narrow mate-in-one
practice flow exist. The current automatic detector and plan cover mate in one
only. Static fork/pin/hanging-piece geometry and structures are observations,
not proven decision failures; the explanation adapter is optional and not in the
automatic coach. Comparable best/played evaluations, multi-skill coaching,
verified own-game/canonical practice, repertoire advice and private Study upload
remain mandatory. The vision’s approximately 215 skills are a roadmap, not a
claim of implemented detectors or calibrated coverage.

## Mandatory phases

0. Release contract and truthful capability registry.
1. Same-position best/played analysis, selective deep verification and a
   versioned competency graph.
2. Validated tactical and defensive opportunities, grounded positional lessons
   and elementary endgames.
3. Recurring patterns with context and source-linked explanations, including
   probes that distinguish observations from hypotheses.
4. Own-game, public and canonical exercises, related retrieval and fair
   alternative-aware grading.
5. Multi-skill curriculum, prerequisites, difficulty, FSRS and separate
   practice/game progress.
6. Named structures, opening DAGs, contextual style and concrete current-line
   and new-opening recommendations.
7. Personalized courses, validated annotated chapters and verified private
   Lichess Studies.
8. Bounded processing, migration, private browser, recovery and deployment.

No optional Maia or bulk handoff optimization substitutes for a mandatory phase.

## Delivery issues

The following 47 issues implement the mandatory phases; the parent issue records dependencies and the final release gate.

### Phase 0 — Release contract

- [#120: Make the adaptive-coach release contract and coverage visible](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/120)

### Phase 1 — Trustworthy analysis

- [#121: Inspect comparable best-move and played-move analysis for each learner decision](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/121)
- [#167: Select and inspect bounded critical positions for deeper analysis](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/167)
- [#168: Resume bounded deep decision analysis with native alternatives and isolated provenance](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/168)
- [#122: Integrate and benchmark the bounded selective deep-analysis pipeline](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/122)
- [#123: Publish a versioned competency graph with honest detector and task coverage](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/123)

### Phase 2 — Useful opportunity detection

- [#124: Coach repeated missed free-material captures and preventable piece losses](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/124)
- [#125: Detect and explain missed and executed forks in the automatic learner pipeline](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/125)
- [#126: Recognize recurring fork-defense failures and successful prevention](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/126)
- [#127: Add verified pin opportunities to learner coaching](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/127)
- [#128: Coach executed, missed and prevented skewers with verified consequences](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/128)
- [#129: Coach discovered attacks and forcing double checks from real decisions](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/129)
- [#130: Explain missed mates and back-rank threats without inventing psychological causes](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/130)
- [#131: Teach concrete threat responses and distinguish effective defensive alternatives](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/131)
- [#132: Teach pawn-weakness plans from actual decisions without labeling structure as failure](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/132)
- [#133: Coach open-file occupation and rook-activity plans from verified alternatives](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/133)
- [#134: Explain king-safety changes and concrete defensive plans](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/134)
- [#135: Coach elementary pawn endgames with verified promotion and opposition tasks](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/135)

### Phase 3 — The coaching product

- [#136: Show recurring weaknesses, successes and contextual blind-spot candidates across games](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/136)
- [#137: Explain recurring patterns with coach-like lessons grounded in stored evidence](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/137)
- [#141: Use targeted recognition and evaluation probes to test coaching hypotheses](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/141)

### Phase 4 — Relevant practice material

- [#169: Stage and publish immutable puzzle corpus versions in bounded SQLite batches](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/169)
- [#170: Acquire official puzzle snapshots with safe resumable downloads and resource limits](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/170)
- [#138: Activate and measure the broad indexed Lichess puzzle library on Hermes](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/138)
- [#139: Add licensed public PGN libraries and canonical endgame/strategy training positions](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/139)
- [#140: Practice own-game and canonical positions through a unified legal session](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/140)
- [#142: Retrieve unfamiliar puzzles that train the same pattern as a learner mistake](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/142)
- [#143: Provide accessible board interaction and lesson navigation for all training sources](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/143)
- [#144: Verify alternative learner moves against the stated exercise objective](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/144)
- [#145: Integrate multi-skill graded attempts with evidence, FSRS and useful feedback](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/145)

### Phase 5 — Adaptive learning

- [#146: Select a diversified daily curriculum from recurring weaknesses and prerequisites](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/146)
- [#147: Track practice gains and recurrence in subsequent games without conflating them](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/147)

### Phase 6 — Style and repertoire

- [#148: Recognize IQP and Carlsbad structure episodes and their common plans](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/148)
- [#149: Recognize French, Caro-Kann and Benoni pawn skeletons in learner games](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/149)
- [#150: Recognize Maroczy, Hedgehog and Sicilian structural patterns](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/150)
- [#151: Load opening reference data and expose the learner's transposition-aware repertoire](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/151)
- [#152: Measure comparable material/activity and simplification choices with context](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/152)
- [#153: Extend the style profile to attack, defense, centers and endgame transitions](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/153)
- [#154: Build evidence-backed opening profiles for comparing fit and learning value](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/154)
- [#155: Recommend concrete improvements to the learner's current opening lines](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/155)
- [#156: Recommend suitable new openings and bounded learning experiments](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/156)

### Phase 7 — Personalized courses

- [#157: Generate versioned personalized courses from weak patterns and opening choices](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/157)
- [#158: Export personalized lessons as annotated, validated Lichess Study chapters](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/158)
- [#159: Create and verify a private Lichess Study for a previewed course version](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/159)
- [#160: Resume private Lichess chapter uploads safely and verify complete courses](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/160)

### Phase 8 — Integrated release

- [#161: Operate the complete coaching and course pipeline within private Hermes budgets](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/161)
- [#162: Verify and deploy the complete personalized coach and private Lichess courses](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/162)

Issues #167 and #168 implement selection and execution; #122 integrates those bounded queues into the automatic worker and documents a synthetic budget proxy. Issues #169 and #170 implement staging and acquisition needed by #138. The integration issues retain the original end-to-end acceptance outcomes.

Earlier related issues [#46](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/46), [#47](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/47), [#48](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/48), [#49](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/49), [#52](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/52) and [#53](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/53) remain relevant product history.

## Release acceptance scenarios

Implement these as reproducible integration fixtures using only synthetic games,
positions, accounts and course content. Fixtures must not enter the real learner
profile. Each scenario must assert source/version lineage and expected UI or CLI
behavior, not just database rows. They are future release gates; registry and
interface tests in this slice do not claim to satisfy them.

1. **Repeated non-mate patterns.** Analyze at least three independent synthetic
   games with a manually validated fork opportunity, including a success, failure
   and ambiguous case, and at least one defensive opportunity. After review, the
   report names the skill and operation, counts opportunities and outcomes,
   shows source decisions and contexts, and does not infer why a move was missed.
   A repeated position or multiple moves in one game must not inflate mastery.
2. **Distinct sources and correct alternatives.** Generate a verified exercise
   from a learner game and retrieve a related unfamiliar public puzzle and a
   canonical task. Each has distinct source provenance and a legal solution.
   Submit a second objectively correct move and a wrong move; the former must
   not be falsely failed. A move whose correctness cannot be established is
   ungraded. Complete and review tasks, then verify scheduling and eligible
   evidence without counting repeated prompts twice.
3. **Sparse and confounded evidence.** Use fewer than three independent reviewed
   contexts, duplicate imports, an unreviewed/ambiguous fact, and a position
   reached in time trouble. The report must expose exclusions and uncertainty,
   avoid a supported weakness from sparse data, and retain clock/time-control
   context without asserting a cause. Old or revoked evidence invalidates stale
   conclusions. Practice improvement and later game recurrence remain separate.
4. **Opening recommendations.** Supply synthetic opening histories and a
   reference repertoire with known transpositions and sample limits. Verify a
   concrete improvement to a current line and a separate new-opening experiment,
   each with legal moves, supporting positions, uncertainty and competitive vs.
   developmental rationale. Sparse input must be identified rather than filled
   with invented conclusions.
5. **Private course verification.** Generate and preview synthetic course
   chapters with legal annotated PGN, upload using an isolated test account to a
   private Study, then read back ownership, privacy and chapter content. A retry
   must reconcile rather than duplicate; a denied or unavailable upload remains
   incomplete and never falls back to public publication. A live authorized
   private upload and returned usable link are required before release.

All release scenarios must pass with the required checks, exact-head independent
review, private deployment verification and backup/restore evidence before #119
closes. The real learner’s data and credentials must not appear in fixtures,
tracked files, issues or logs.

## Review policy during provider unavailability

The user authorized an independent Sol review of each exact final head and green
CI as the review gate while Greptile is unavailable. Address all available
review findings; this policy does not claim that an unavailable provider has
reviewed the change. Existing exact-head and release acceptance requirements
remain in force.
