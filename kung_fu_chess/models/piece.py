class Piece:
    def __init__(self, token: str):
        # token example: 'wK', 'bP', '.' for empty
        self.token = token

    @property
    def is_empty(self) -> bool:
        return self.token == '.'

    @property
    def color(self):
        return None if self.is_empty else self.token[0]

    @property
    def type(self):
        return None if self.is_empty else self.token[1]

    def __repr__(self):
        return f"Piece('{self.token}')"
