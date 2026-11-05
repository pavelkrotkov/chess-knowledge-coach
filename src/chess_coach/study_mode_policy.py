"""Recognize the provider's verified chapter modes."""


def valid(chapter, mode):
    if mode == "gamebook":
        return chapter.get("gamebook") is True and chapter.get("conceal") is None
    return mode == "conceal" and chapter.get("conceal") is not None and not chapter.get("gamebook")
