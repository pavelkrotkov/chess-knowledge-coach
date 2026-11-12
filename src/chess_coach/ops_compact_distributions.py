"""Check installed distribution versions against the exact frozen lock."""

import re
import tomllib


def distributions(lock, installed):
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    expected = {item["name"]: item["version"] for item in packages}
    names = set()
    for name, version in installed:
        name = re.sub(r"[-_.]+", "-", name.lower())
        if name in names or expected.get(name) != version:
            raise ValueError("dependency distribution differs from the lock")
        names.add(name)
    if not names:
        raise ValueError("dependency distributions unavailable")
