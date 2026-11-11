"""Select first-encounter knight-fork cohorts within a bounded session window."""

import json
from collections import defaultdict

from .fork_followup_first import first
from .fork_progress_scope import scope
from .fork_progress_window import rows
from .mastery_time import parse_utc


def select(db, subject, corpus, budget):
    with budget.scope(snapshot=False):
        selected, window_limited, tied = rows(db, subject, corpus)
    groups, limited = defaultdict(list), tied
    for row in selected:
        try:
            with budget.scope(snapshot=False):
                when = parse_utc(row["started_at"])
                if when is None or when.isoformat() != row["started_at"]:
                    limited = True
                    continue
                try:
                    context = scope(row, corpus)
                except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                    limited = True
                    continue
                if context is None:
                    continue
                try:
                    first(db, subject, row)
                except ValueError:
                    continue
                key = json.dumps(context, sort_keys=True, separators=(",", ":"))
                groups[key].append(row)
        except (TypeError, KeyError, IndexError, AttributeError):
            limited = True
    return list(groups.values()), limited, window_limited
