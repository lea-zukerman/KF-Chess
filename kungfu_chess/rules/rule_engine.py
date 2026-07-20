from .piece_rules import is_legal_move


class RuleEngine:
    def __init__(self, board):
        self.board = board

    def is_legal(self, from_row, from_col, to_row, to_col):
        token = self.board._grid[from_row][from_col]
        return is_legal_move(token, from_row, from_col, to_row, to_col, self.board._grid)
