"""Add checking evidence only after source, score and history validation."""

from .style_check_lines import events


def annotate(board, compared, budget):
    played = events(board, compared["played"], budget)
    for pair in compared["pairs"]:
        pair["played"]["check_events"] = played
        pair["alternative"]["check_events"] = events(board, pair["alternative_line"], budget)
