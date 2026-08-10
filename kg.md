# Chess Knowledge Graph / Adaptive Coach

## Goal

Local-first tutor on 2010 Mac mini:

```text
Lichess games
→ Stockfish + deterministic facts
→ versioned skill evidence
→ mastery/style/structure/repertoire state
→ adaptive training
→ FSRS review
→ LLM explanation
```

Think **Math Academy for chess**, not “engine review + memory.”

Novel layer:

> game events → credible skill evidence → learner model → curriculum

Reuse everything else.

---

## Architecture

```text
Lichess + clocks
    ↓
immutable raw games
    ↓
versioned analysis
 ├ Stockfish 18
 ├ opening classification
 ├ structure extraction
 ├ deterministic detectors
 └ optional Maia-3
    ↓
versioned evidence mapper
    ↓
skill evidence
    ↓
mastery | style | structure | repertoire
    ↓
curriculum
    ↓
own positions + Lichess puzzles
    ↓
FSRS
    ↓
training attempts ↺
```

LLM:

- explains;
    
- summarizes;
    
- proposes causal hypotheses.
    

LLM does **not** own board truth, engine eval, facts, history, or mastery.

---

## Data Model

### Immutable

- PGN/FEN/move;
    
- clocks/time control;
    
- ratings/game metadata.
    

### Versioned analysis

- Stockfish output;
    
- opening/structure facts;
    
- deterministic motifs;
    
- optional Maia output.
    

Store provenance:

```text
engine/model/version
NNUE/checkpoint
nodes/depth/MultiPV
threads/hash
detector/ontology/mapper version
```

### Versioned inference

Skill attribution is recomputable:

```yaml
skill: fork
operation: prevent
outcome: failure
confidence: .88
source_facts: [...]
```

Facts are immutable; diagnoses are not.

---

## Longitudinal State

Keep separate:

1. **Mastery** — what I can do.
    
2. **Style** — what I prefer / handle well.
    
3. **Structure history** — positions I actually reach.
    
4. **Repertoire** — openings and resulting positions.
    

Also retain:

```text
rating
time control
clock
move time
game phase
opening familiarity
```

to avoid mistaking context for style.

---

## Skill Ontology

No mature open-source Math-Academy-like chess competency graph found.

Bootstrap from:

- Lichess puzzle themes;
    
- ChessQA taxonomy/tests;
    
- CARA detectors;
    
- standard tactics/strategy/endgame/structure curricula.
    

Current:

```text
~215 canonical skills
```

Edges:

```text
IS_A
REQUIRES
SUPPORTS
RELATED_TO
CONTRASTS_WITH
TRAINED_BY
EVIDENCED_BY
```

Represent operation separately:

```text
skill = fork
operation = recognize | calculate | execute | prevent | evaluate
```

Do not create five ontology nodes per skill.

Important:

- `execute` / often `prevent` observable in games;
    
- `recognize` / `calculate` / `evaluate` largely latent;
    
- targeted training gives cleaner evidence for latent operations.
    

---

## Evidence

Generate evidence from **opportunities**, not every move.

```text
fork threat exists
→ player had meaningful response opportunity
→ prevented / missed / ambiguous
```

Rules:

- collect success and failure;
    
- CPL ≠ skill failure;
    
- Stockfish match ≠ mastery;
    
- distinguish fact from cause;
    
- preserve ambiguity;
    
- retain raw evidence for reprocessing.
    

---

## Stockfish

Use **Stockfish 18** upstream; Ubuntu package may lag.

2010 Mini is adequate for selective CPU analysis.

Check:

```bash
lscpu
grep -m1 '^flags' /proc/cpuinfo
```

Use compatible POPCNT/generic x64 build.

Prefer:

```text
cheap fixed-node scan
→ critical positions
→ larger node budget
```

Store:

```text
score/WDL before+after
best move
played move
PV
nodes
engine version
```

Prefer expected-score/WDL loss over raw CPL where useful.

---

## Maia-3

Optional human-behavior model.

Current Maia-3:

- UCI;
    
- CPU mode;
    
- Elo conditioning;
    
- MultiPV human move probabilities;
    
- 5M / 23M / 79M models.
    

Use:

```text
Stockfish → move quality
Maia      → human/rating-level likelihood
```

Never mix Maia “eval” with Stockfish eval.

On Mini:

- test 5M in separate venv;
    
- old CPU/PyTorch may fail or be slow;
    
- otherwise run Maia on newer hardware and persist results.
    

Not a v1 dependency.

---

## Detectors

### ChessQA

Use for:

- taxonomy;
    
- motif definitions;
    
- tests/benchmark ideas.
    

Not primary production detector library.

### CARA

Use/study for:

- deterministic tactical/positional rules;
    
- post-game motif detection.
    

Build manually validated detector tests before mastery inference.

---

## Openings

Use Lichess `chess-openings` directly:

- ECO;
    
- names;
    
- PGN/UCI;
    
- EPD;
    
- transpositions;
    
- CC0.
    

Represent repertoire as **position graph/DAG**, not move-prefix tree.

Track:

```text
position
→ frequency
→ performance
→ structures
→ skill demands
→ style demands
```

---

## Structures

Extract atomic features first:

```text
isolated pawn
hanging pawns
backward pawn
open/half-open files
locked center
space
minority structure
...
```

Derive named structures:

```text
IQP
Carlsbad
Maroczy
Hedgehog
Benoni
French
Caro-Kann
Sicilian
...
```

Store episodes:

```text
start_ply
end_ply
features
structure
confidence
```

Do not force one exclusive structure label.

---

## Style

Track dimensions, not labels:

```text
tactical complexity
initiative
material vs activity
simplification
king attacks
defense
open/closed centers
queenless middlegames
endgame transitions
```

For each:

```text
preference
performance
opportunities
uncertainty
trend
```

Best preference evidence:

> multiple similarly evaluated moves → repeated choice of one position type

Control for clock/time control/rating/opening familiarity.

---

## Repertoire

Model each opening by:

```text
structure distribution
skill demands
style fit
performance
switching distance
```

Answer:

- what suits my style?
    
- what lines create weak structures?
    
- what opening trains a weakness?
    
- lowest-cost repertoire change?
    
- has my style changed?
    

Optimize separately:

```text
competitive fit
developmental value
```

Avoid comfort-zone maximization.

---

## Mastery

Derived state only.

Avoid fake-calibrated chess Elo:

```text
fork.prevent = 1410 ± 65
```

unless item difficulty is genuinely calibrated.

Prefer initially:

```yaml
fork.prevent:
  mastery: .64
  uncertainty: .09
  evidence: 21.3
  trend_30d: +.07
```

Puzzle ratings provide useful item difficulty; game opportunities usually do not.

Start simple + probabilistic.

Later benchmark:

- Elo/IRT;
    
- pyBKT;
    
- custom hierarchical model.
    

Do not optimize mastery math before validating evidence.

---

## Training

Separate:

```text
WHAT → mastery/curriculum
WHEN → FSRS
```

Sources:

- critical positions from own games;
    
- Lichess puzzles;
    
- canonical endgames/strategy positions;
    
- diagnostic probes.
    

Priority:

```text
weakness
× confidence
× frequency
× importance
× expected benefit
× forgetting
```

FSRS schedules **training items**, not skills.

---

## Lichess Puzzle Corpus

Use bulk local database, not API as primary source.

~6M puzzles with:

```text
FEN
solution
rating/RD
themes
popularity
source game
opening tags
```

Download:

```text
lichess_db_puzzle.csv.zst
```

Index by:

```text
theme
rating
opening
structure
training objective
```

Ready-made adaptive item bank.

---

## Reuse

### Direct

```text
chess / python-chess
Stockfish 18
berserk
httpx
Lichess chess-openings
Lichess puzzle DB
fsrs
SQLite
```

### Selective / study

```text
Chessli / Chessli2 → ingestion/training workflow
CARA              → deterministic detectors
ChessQA            → taxonomy/tests
En Croissant       → analysis/repertoire/SRS ideas
pyBKT              → mastery baseline
```

### Optional

```text
Maia-3
```

### Avoid as foundation

```text
Neo4j
Prolog
RDF chess ontologies
PostgreSQL
Redis
vector DB
Docker
```

unless a concrete need emerges.

---

## SQLite

Tables:

```text
skills
skill_edges

games
positions

analysis_runs
engine_outputs
detector_facts
evidence_mappings

structural_episodes

player_skill_state
style_observations
style_state
repertoire

training_items
training_attempts
```

SQLite recursive CTEs are enough for ontology traversal.

---

## Mini Setup

```bash
set -e
sudo apt update
sudo apt install -y \
  git curl ca-certificates jq sqlite3 \
  python3 python3-venv python3-pip python3-dev \
  build-essential zstd

mkdir -p ~/chess-knowledge
cd ~/chess-knowledge
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install \
  berserk chess httpx pyyaml pydantic sqlalchemy fsrs
```

Install upstream Stockfish 18 separately.

Do not install Maia/PyTorch in base environment.

---

## Build Order

1. Lichess ingestion + clocks.
    
2. Analysis provenance.
    
3. Stockfish 18 pipeline.
    
4. Opening classification.
    
5. Atomic structures.
    
6. Deterministic detectors.
    
7. Detector tests.
    
8. Fact → skill mapping.
    
9. Raw longitudinal evidence reports.
    
10. Human validation.
    
11. Simple mastery model.
    
12. Local puzzle corpus.
    
13. Targeted training.
    
14. FSRS.
    
15. Named structures.
    
16. Style model.
    
17. Repertoire recommender.
    
18. Maia-3 test/enrichment.
    
19. LLM explanations.
    
20. Lichess Study publishing.
    

Critical gate:

> Do not build sophisticated mastery state until evidence reports make chess sense.

---

## Validation

First produce reports such as:

```text
Last 50 games

fork.prevent
  opportunities 17
  success        9
  failure        6
  ambiguous      2

back_rank.prevent
  opportunities 11
  success       10
  failure        1
```

If these are wrong, fix detection/mapping—not the mastery model.

---

## Cost

Core software: effectively **$0**.

Potential recurring cost:

- hosted LLM inference.
    

2010 Mini is sufficient for core pipeline; newer hardware may be useful for Maia/bulk re-analysis.

---

## Principle

Do not build another chess-analysis app.

Reuse:

```text
games
engines
openings
puzzles
basic detectors
review scheduling
```

Build:

```text
game events
→ reproducible facts
→ versioned skill evidence
→ longitudinal learner state
→ adaptive curriculum
→ training evidence
→ improved learner state
```

Highest-risk component:

> **reliable skill evidence**, not Stockfish, Lichess, storage, or LLMs.
