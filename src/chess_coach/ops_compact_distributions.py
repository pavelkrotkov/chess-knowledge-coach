"""Check installed distribution versions against the exact frozen lock."""

import re
import tomllib


def distributions(lock, installed):
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    expected = {}
    for item in packages:
        name = re.sub(r"[-_.]+", "-", item["name"].lower())
        if name in expected:
            raise ValueError("duplicate dependency name in the lock")
        expected[name] = item["version"]
    names = set()
    for name, version in installed:
        name = re.sub(r"[-_.]+", "-", name.lower())
        if name in names or expected.get(name) != version:
            raise ValueError("dependency distribution differs from the lock")
        names.add(name)
    if not names:
        raise ValueError("dependency distributions unavailable")
