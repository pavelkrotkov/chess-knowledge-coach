"""Offer the finder only for a current matching owned defense source."""


def available(evidence):
    try:
        if (
            evidence["back_rank_source_currentness"] != "current"
            or evidence["operation"] != "prevent"
            or evidence["outcome"] != "failure"
            or evidence["review_status"] not in {"accepted", "unreviewed"}
        ):
            return False
        import chess

        from .related_backrank_defense_source import _witness

        _witness(evidence["facts"][0]["payload"]["defense"], chess.Board(evidence["decision_fen"]))
        return True
    except (ValueError, TypeError, KeyError, IndexError):
        return False
