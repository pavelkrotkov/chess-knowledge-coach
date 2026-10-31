"""Normalize only the provider-generated checkmate result annotation."""


def comment(node, provider):
    comment = " ".join(node.comment.split())
    if provider and not node.variations and node.board().is_checkmate():
        winner = "0-1 Black" if node.board().turn else "1-0 White"
        if comment == winner + " wins by checkmate.":
            return ""
    return comment
