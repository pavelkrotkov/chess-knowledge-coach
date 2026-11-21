"""Explicit version identities for owned capture objectives."""

TARGET_VERSION = "capture-target-own-v1"
GAIN_VERSION = "capture-gain-own-v1"
TARGET_OBJECTIVE = "capture-target-v1"
GAIN_OBJECTIVE = "capture-gain-v1"
VERSIONS = {TARGET_VERSION, GAIN_VERSION}


def valid_key(version, key):
    return version in VERSIONS and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
