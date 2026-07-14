class RuleEngine:
    def __init__(self, board):
        self.board = board

    def is_legal(self, from_row, from_col, to_row, to_col):
        token = self.board._grid[from_row][from_col]
        return self.board._is_move_legal(token, from_row, from_col, to_row, to_col)
