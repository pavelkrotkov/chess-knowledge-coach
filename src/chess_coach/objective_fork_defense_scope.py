"""Reject fork-defense roots whose history or legal status is unsupported."""


def supported_root(board):
    return (
        board.is_valid()
        and not board.is_check()
        and board.ep_square is None
        and not board.is_game_over(claim_draw=True)
        and not board.is_repetition(2)
    )
