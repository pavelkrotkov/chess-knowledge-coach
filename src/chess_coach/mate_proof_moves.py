"""Legal move rendering, immediate mates, and a shared node budget."""

from dataclasses import dataclass


@dataclass
class Budget:
    limit: int = 6000
    nodes: int = 0

    def visit(self):
        if self.nodes >= self.limit:
            return False
        self.nodes += 1
        return True


def move_view(board, move):
    return {"uci": move.uci(), "san": board.san(move)}


def immediate_mates(board):
    mates = []
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        view = move_view(board, move)
        board.push(move)
        if board.is_checkmate():
            mates.append(view)
        board.pop()
    return mates
