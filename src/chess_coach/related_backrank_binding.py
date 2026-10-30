"""Bind the selected source root and timing to a back-rank transfer."""


def add_fields(binding, source, motif):
    if motif == "backrank_attack":
        binding["mate_timing"] = source["objective"]
        binding["root_move"] = source["provenance"]["selected_root"]
