"""Bounded, descriptive style choices with current source lineage."""

from collections import Counter

from .recurrence_snapshot import read_snapshot
from .repertoire_sources import MAX_GAMES
from .style_protection_budget import MAX_WORK as PROTECTION_WORK_LIMIT
from .style_protection_budget import create as protection_budget
from .style_purpose_collect import collect_game
from .style_purpose_prepare import prepare
from .style_schedule_status import status as schedule_status
from .style_sources import source_games
from .style_summary import summarize

VERSION = "style-choices-v11"
MATE_SEARCH_LIMIT = 100


def style_report(db, learner, *, max_games=MAX_GAMES):
    with read_snapshot(db):
        return _style_report(db, learner, max_games=max_games)


def _style_report(db, learner, *, max_games):
    source = source_games(db, learner, max_games=max_games)
    counts = Counter(
        {
            "selected": 0,
            "completed": 0,
            "played_root_covered": 0,
            "comparable": 0,
            "stale_selection": 0,
            "games_without_selection": 0,
            "selected_without_learner_context": 0,
            "selection_eligible": 0,
            "selection_capped_out": 0,
            "selection_omitted_critical": 0,
            "selection_missing_scores": 0,
            "selected_in_check": 0,
            "comparable_in_check": 0,
            "forced_check": 0,
            "outside_check": 0,
            "check_context_unknown": 0,
        }
    )
    allocations, observations = Counter(), []
    budget = {
        "limit": MATE_SEARCH_LIMIT,
        "examined": 0,
        "completed": 0,
        "unsupported": 0,
        "skipped": 0,
        "protection": protection_budget(limit=PROTECTION_WORK_LIMIT),
    }
    purpose = prepare(db, learner, source["games"])
    for game in source["games"]:
        game_counts, game_allocations, items = collect_game(db, learner, game, budget, purpose)
        counts.update(game_counts)
        allocations.update(game_allocations)
        observations.extend(items)
    observations.extend(purpose["observations"])
    counts["unselected_decisions"] = max(
        0, source["decisions"] - counts["selected"] + counts["selected_without_learner_context"]
    )
    return {
        "version": VERSION,
        "purpose_schedule": schedule_status(
            db, learner, views=purpose["views"], protection_checks=purpose["protection_checks"]
        ),
        "purpose_coverage": {
            **purpose["limits"],
            "counts": dict(purpose["counts"]),
            "sample_note": "Check and protection targets and deterministic controls are small, biased samples; overlapping allocations share one decision. Older cycles and excluded records remain unknown.",
        },
        "transition_method": (
            "Four-ply conditional projections, not observed outcomes or intent: queenless "
            "contrasts zero queens with one per side from such a root; imbalanced "
            "endpoints are ambiguous. A low-material transition contrasts fewer than six "
            "non-pawn pieces with six or more from a root with at least six; this is a "
            "phase proxy, not proof of an endgame. Standard-start verified history, "
            "nonterminal non-repeated positions and non-promotion lines are required. "
            "Comparable roots have exact same-depth scores within 50 cp at depth >= 4."
        ),
        "center_method": (
            "The four-ply conditional lines compare specific opposing pawn contacts with at "
            "least one pawn on the d/e file (pairs list white square then black square); "
            "legal pawn-on-pawn captures touching d/e; "
            "consecutive pawn recaptures of the same capturing pawn; newly pawn-free d/e "
            "files; and the exact d4/e4 white and d5/e5 black locked skeleton. Events list "
            "their side and ply and can be opponent moves. These are narrow proxies, not "
            "universal open or closed centers, actual outcomes or learner intent. Opposing "
            "contrasts are ambiguous and no contrast is not evidence of preference."
        ),
        "checking_method": (
            "Checks are legal moves, with all legal evasions listed when the 100-move "
            "budget permits. Root-check choices exclude positions already in check. "
            "A third-ply learner check and any legal immediate-mate witness are conditional "
            "on the specific opponent reply at ply two, not forced threats or actual future "
            "moves. Positions already in check, draw-sensitive histories, promotions and "
            "exhausted budgets are unsupported for the conditional mate witness. Each report "
            "examines at most 100 candidate continuation boards in selected game-start "
            "order; additional candidates are unknown, not negative. Root and third-ply "
            "checking counts are unaffected by this cap. Opponent "
            "checks are recorded separately. These observations do not establish initiative, "
            "attacking intent, skill or causal game outcomes; broader king threats remain "
            "unsupported. Existing same-search, same-depth CP gates are unchanged."
        ),
        "defense_method": (
            "Only legal root responses while already in check are compared. King moves, "
            "captures, interpositions against one sliding checker and counterchecks may overlap; "
            "they are not independent observations. Captures identify the captured piece and "
            "square, which need not be the checker. A legal evasion does not prove subsequent "
            "safety, compensation or overall defense quality. Forced, unscored, stale, missing "
            "and unsupported choices are unknown; non-check decisions are outside this family. "
            "Broader threats and unqualified piece protection remain unsupported. Each contrast "
            "requires the same current, same-search, same-depth exact CP gate as other choices."
        ),
        "protection_method": (
            "A purpose comparison and its independently owned original protection source must both be current within the same read snapshot. Only a unique owned protection source "
            "with original history is eligible. Later requests recheck it. "
            "The same-search choices are compared only when each bounded verifier supports "
            "the same originally threatened piece. Moving that piece and capturing a proved "
            "immediate attacker are distinct, potentially overlapping events. An unmoved "
            "piece is not proof of a guard; guard, checking counterplay, compensation, "
            "other captures and longer threats remain unknown where the model cannot prove "
            "them. The result concerns supported immediate captures only, not overall "
            "safety or the outcome of the game. At most 20 report-wide source-lookup, "
            "source-resolution, threat-probe and proof work units are reserved; source "
            "resolution includes currentness and witness checks and an exemplar proof; "
            "root proofs use a one-second limit. Skipped and unsupported decisions are "
            "unknown. The work limit is not a wall-clock guarantee."
        ),
        "sample_note": (
            "Games with verified UTC start and ownership are selected by game-start time; "
            "local ID breaks exact ties without implying chronology. Unknown or stale "
            "records cannot be placed and are excluded with explicit coverage. Historical "
            "ingest may have normalized duplicate original tags before storage; such lost "
            "ambiguity cannot be recovered. "
            "Selection and decision counts apply only to retained games; unprocessed games "
            "and their decisions are unknown when the sample, scan, replay or duplicate "
            "limits exclude records. No outcome or preference is inferred for those records."
        ),
        "familiarity_note": (
            "Familiarity is unknown: game-start timestamps do not date individual decisions. "
            "Earlier-started games may reach the position later; this count is not prior exposure."
        ),
        "trend_note": (
            "Groups use game-start timestamps; overlapping games do not establish decision order."
        ),
        "coverage": {key: value for key, value in source.items() if key != "games"},
        "selection_counts": dict(counts),
        "checking_coverage": {key: value for key, value in budget.items() if key != "protection"},
        "protection_coverage": budget["protection"],
        "allocations": dict(allocations),
        "dimensions": summarize(observations),
        "observations": observations,
    }
