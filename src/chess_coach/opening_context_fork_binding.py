"""Bind one unfamiliar public branch and the existing fork proof policy."""

from .fact_fingerprint import canonical, digest
from .opening_profile_game import EXTENDED_PLIES
from .opening_profile_play import STORED_PLIES
from .opening_public_proof_source import PROOF_SECONDS, SECONDS
from .opening_public_proof_versions import combined
from .opening_reference_source import SOURCE_ARCHIVE

VERSION = "opening-context-public-fork-v1"


def key(selection):
    names = ("color", "parent", "path", "move", "child")
    return digest(canonical([VERSION, {name: selection[name] for name in names}]))


def binding(item):
    source, selection = item["source"], item["selection"]
    line, profile = source["line"], source["profile"]
    policy = combined({"policy": {}})["policy"]["fork"]
    return {
        "version": VERSION,
        "selection": selection,
        "source": {
            "record": line["record"],
            "reference": line["reference"],
            "line_sha256": digest(canonical(line)),
            "history": source["source_history"],
            "source": profile["source"],
            "source_archive": SOURCE_ARCHIVE,
            "source_sha256": profile["source_sha256"],
            "license": profile["license"],
            "license_url": profile["license_url"],
            "index_sha256": selection["reference_index_sha256"],
            "filter": "exact public record, parent and candidate branch",
        },
        "policy": {
            **policy,
            "window_plies_including_branch": EXTENDED_PLIES,
            "post_branch_only": True,
            "stored_plies": STORED_PLIES,
            "records": 1,
            "shared_seconds": SECONDS,
            "proof_seconds": PROOF_SECONDS,
        },
    }
