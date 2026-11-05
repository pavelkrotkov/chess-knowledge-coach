"""Check ordered game linkage and independent cached decisions."""


def _unique_positions(item):
    positions = [row[0] for row in item["results"]]
    return len(positions) == len(set(positions))


def _linked(games, checked):
    order = {row[0]: (index, row[1]) for index, row in enumerate(checked)}
    prior = -1
    for item in games:
        entry = order.get(item["id"])
        if not entry or entry[0] <= prior or entry[1] != item["signature"]:
            return False
        prior = entry[0]
    return True


def _independent(games):
    identities = [item["identity"] for item in games]
    positions = [row[0] for item in games for row in item["results"]]
    return len(identities) == len(set(identities)) and len(positions) == len(set(positions))


def _retained(data, checked):
    consumed = {str(row[0]) for row in checked}
    return all(
        key == str(item["id"]) and key not in consumed and _unique_positions(item)
        for key, item in data["retained"].items()
    )


def valid_relations(data, checked):
    return (
        _linked(data["games"], checked) and _independent(data["games"]) and _retained(data, checked)
    )
