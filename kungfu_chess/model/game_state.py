class GameState:
    def __init__(self, white_name: str = "White", black_name: str = "Black"):
        self.current_turn = 'w'
        self.white_name = white_name
        self.black_name = black_name

    def switch_turn(self):
        self.current_turn = 'b' if self.current_turn == 'w' else 'w'

    def current_player_name(self) -> str:
        return self.white_name if self.current_turn == 'w' else self.black_name
