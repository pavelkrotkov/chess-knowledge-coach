"""Replay the bounded recorded line with the original draw history."""


def replay(board, moves):
    child, san, uci = board.copy(), [], []
    for text in moves[:8]:
        if child.is_game_over(claim_draw=True):
            break
        try:
            candidate = child.parse_uci(text)
        except ValueError:
            return None
        san.append(child.san(candidate))
        uci.append(text)
        child.push(candidate)
    return {"uci": uci, "san": san}
