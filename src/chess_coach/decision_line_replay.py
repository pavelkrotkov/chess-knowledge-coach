"""Replay a recorded PV with the original game history to produce legal SAN."""


def replay_line(board, pv, role, played):
    replay = board.copy()
    san = []
    moves = (pv or "").split()
    if role == "played" and moves and moves[0] != played:
        raise ValueError("played line has a different root")
    for text in moves:
        move = replay.parse_uci(text)
        san.append(replay.san(move))
        replay.push(move)
    return {"san": san, **_terminal(replay, moves)}


def _terminal(board, moves):
    outcome = board.outcome(claim_draw=False) if moves else None
    if outcome is None:
        return {"terminal": None, "terminal_reason": None}
    return {"terminal": outcome.result(), "terminal_reason": outcome.termination.name.lower()}
