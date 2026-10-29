"""Build indexed corpus and theme queries with bounded pagination."""


def build_query(
    corpus_id, state, theme, operation, min_rating, max_rating, after_rating=None, after_id=None
):
    indexed_theme = theme is not None and state == "ready"
    query, params, order, rating = _base(corpus_id, theme, indexed_theme)
    if operation is not None:
        query += " AND p.objective=?"
        params.append(operation)
    if min_rating is not None:
        query += f" AND {rating}>=?"
        params.append(min_rating)
    if max_rating is not None:
        query += f" AND {rating}<=?"
        params.append(max_rating)
    if after_rating is not None:
        key = "t.puzzle_id" if indexed_theme else "p.puzzle_id"
        query += f" AND ({rating},{key})>(?,?)"
        params.extend((after_rating, after_id))
    return query + " ORDER BY " + order, params


def _base(corpus_id, theme, indexed_theme):
    if indexed_theme:
        query = """SELECT p.* FROM puzzle_themes t
        JOIN puzzles p ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
        WHERE t.corpus_id=? AND t.theme=?"""
        return query, [corpus_id, theme], "t.rating,t.puzzle_id", "t.rating"
    query = "SELECT p.* FROM puzzles p WHERE p.corpus_id=?"
    params = [corpus_id]
    if theme is not None:
        query += " AND EXISTS (SELECT 1 FROM json_each(p.themes_json) WHERE value=?)"
        params.append(theme)
    return query, params, "p.rating,p.puzzle_id", "p.rating"
