"""Bounded, descriptive style choices with current source lineage."""

from collections import Counter

from .style_observations import game_observations
from .style_selection import selection
from .style_sources import source_games
from .style_summary import summarize

VERSION = "style-choices-v4"


def style_report(db, learner):
    source = source_games(db, learner)
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
        }
    )
    allocations, observations = Counter(), []
    for game in source["games"]:
        selected = selection(db, game["game_id"], learner)
        if selected is None:
            counts["games_without_selection"] += 1
        game_counts, game_allocations, items = game_observations(db, learner, game, selected)
        counts.update(game_counts)
        allocations.update(game_allocations)
        observations.extend(items)
    counts["unselected_decisions"] = max(
        0, source["decisions"] - counts["selected"] + counts["selected_without_learner_context"]
    )
    return {
        "version": VERSION,
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
        "familiarity_note": (
            "Familiarity is unknown: game-start timestamps do not date individual decisions. "
            "Earlier-started games may reach the position later; this count is not prior exposure."
        ),
        "trend_note": (
            "Groups use game-start timestamps; overlapping games do not establish decision order."
        ),
        "coverage": {key: value for key, value in source.items() if key != "games"},
        "selection_counts": dict(counts),
        "allocations": dict(allocations),
        "dimensions": summarize(observations),
        "observations": observations,
    }
