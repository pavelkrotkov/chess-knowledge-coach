"""Restrict redistribution to declared supported license notices."""


def validate_terms(value):
    notice = " ".join(value["license_notice"].split())
    if value["license"] == "MIT":
        _mit(notice)
    elif value["license"] == "CC0-1.0":
        if "CC0" not in notice or "creativecommons.org/publicdomain/zero/1.0" not in notice:
            raise ValueError("CC0 notice is incomplete")
    else:
        raise ValueError("license is not approved for redistribution")


def _mit(notice):
    required = (
        "Copyright",
        "Permission is hereby granted, free of charge",
        "The above copyright notice and this permission notice shall be included",
        "THE SOFTWARE IS PROVIDED",
    )
    if len(notice) < 800 or not all(part in notice for part in required):
        raise ValueError("MIT notice is incomplete")
