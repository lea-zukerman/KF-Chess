class Position:
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col

    def __iter__(self):
        yield self.row
        yield self.col

    def __repr__(self):
        return f"Position({self.row}, {self.col})"
