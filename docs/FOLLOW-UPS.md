# Follow-up issues (crystallized from the build session)

Decisions and loose ends from the issues 1–10 implementation that did not become
code, captured so they are not lost. Create these as GitHub issues when picked up.

## 1. Human-validation workflow for evidence

The mastery gate stores human validation (a `human_validated` flag plus validation
metadata/timestamps on evidence), and `validate-evidence` already marks items
validated. What is missing is the full review workflow: a CLI flow for a human to
review an evidence report and mark items **rejected** (distinct from unreviewed),
plus richer validation provenance (who validated, when, per item). Needed before
mastery numbers can be trusted end-to-end.

## 2. Training-loop closure: due items → session → outcome → evidence

FSRS scheduling, puzzle corpus, and training attempts exist independently. Wire
them into a loop where training outcomes feed back as *stronger* evidence than
passive game observation (per kg.md's learning loop).

## 3. Style & repertoire views

kg.md defines four player views (mastery, style, structures, repertoire). Only
structures have any implementation. Opening→structure linkage exists in raw form;
the style/repertoire aggregation is unstarted.

## 4. Curriculum selection

Nothing yet selects *what* to train next from the learner model. Requires #1 and #2.

## 5. Bulk-analysis handoff runbook

`merge_analysis_outputs()` exists and is atomic, and the README documents the
handoff at a high level. Missing is an end-to-end runbook for the "analyze on
newer hardware, merge back" workflow (copy DB, run bounded jobs, merge, verify)
plus a smoke test exercising the full path. Write it as docs + a smoke test.

## 6. Maia deployment story

Maia runs via optional subprocess adapter with offline fallback. A concrete setup
(separate env, model download, config) is undocumented; decide whether it stays
optional forever or gets first-class packaging.

## 7. PR #11 merge-state audit

PR #11's merge state was inconclusive during the build (changes present in history,
merge commit unverified). Verify `git log --follow` coverage of its changes on main;
close only after confirming nothing was double-applied or dropped.

## 8. Coverage of ambiguous-evidence paths

Evidence records support success/failure/ambiguous outcomes; tests emphasize success
paths. Add fixtures exercising ambiguity propagation through mastery aggregation.
