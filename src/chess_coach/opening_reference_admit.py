"""Count excluded and duplicate sample records."""


def _duplicate(record, seen, urls):
    return record[0] in seen or bool(record[5] and record[5] in urls)


def admit(record, records, counts, seen, urls):
    if record is None:
        counts["excluded"] += 1
    elif _duplicate(record, seen, urls):
        counts["duplicates"] += 1
    else:
        seen.add(record[0])
        urls.add(record[5])
        counts["unknown_context"] += any(
            value in ("?", "", "????.??.??") for value in record[2].values()
        )
        records.append(record)
